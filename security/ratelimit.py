"""
Redis token bucket.

Chosen over a fixed window because fixed windows allow a 2x burst across the
boundary — 60 requests at 11:59:59 and 60 more at 12:00:00. The bucket
refills continuously, so the limit means what it says.

Implemented as a Lua script so check-and-decrement is atomic. Doing it in two
round-trips lets concurrent requests both see capacity that only one of them
actually has.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from fastapi import HTTPException, status

from db.cache import get_redis

# KEYS[1] = bucket key
# ARGV = capacity, refill_per_second, now, requested
TOKEN_BUCKET_LUA = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local requested = tonumber(ARGV[4])

local bucket = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(bucket[1])
local ts = tonumber(bucket[2])

if tokens == nil then
    tokens = capacity
    ts = now
end

local elapsed = math.max(0, now - ts)
tokens = math.min(capacity, tokens + elapsed * refill)

local allowed = 0
if tokens >= requested then
    tokens = tokens - requested
    allowed = 1
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
redis.call('EXPIRE', key, math.ceil(capacity / refill) * 2)

return {allowed, tokens}
"""

_script_sha: str | None = None


@dataclass
class RateLimitResult:
    allowed: bool
    remaining: float
    limit: int
    retry_after: int


async def _sha() -> str:
    global _script_sha
    if _script_sha is None:
        _script_sha = await get_redis().script_load(TOKEN_BUCKET_LUA)
    return _script_sha


async def check(identity: str, limit_per_minute: int, cost: int = 1) -> RateLimitResult:
    """
    Consume `cost` tokens for `identity`.

    FAILS OPEN if Redis is unavailable. Deliberate: a rate limiter outage
    should degrade to "unlimited", not "service down". The tradeoff is
    acceptable because the limiter protects cost, not correctness.
    """
    key = f"troy:ratelimit:{identity}"
    refill = limit_per_minute / 60.0
    now = time.time()

    try:
        r = get_redis()
        try:
            res = await r.evalsha(await _sha(), 1, key, limit_per_minute, refill, now, cost)
        except Exception:
            # Script cache flushed (e.g. Redis restart) — reload and retry once.
            global _script_sha
            _script_sha = None
            res = await r.eval(TOKEN_BUCKET_LUA, 1, key, limit_per_minute, refill, now, cost)
    except Exception:
        return RateLimitResult(True, float(limit_per_minute), limit_per_minute, 0)

    allowed = bool(int(res[0]))
    remaining = float(res[1])
    retry_after = 0 if allowed else max(1, int((cost - remaining) / refill))

    return RateLimitResult(allowed, remaining, limit_per_minute, retry_after)


async def enforce(identity: str, limit_per_minute: int, cost: int = 1) -> RateLimitResult:
    result = await check(identity, limit_per_minute, cost)
    if not result.allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded ({limit_per_minute}/min)",
            headers={
                "Retry-After": str(result.retry_after),
                "X-RateLimit-Limit": str(result.limit),
                "X-RateLimit-Remaining": "0",
            },
        )
    return result