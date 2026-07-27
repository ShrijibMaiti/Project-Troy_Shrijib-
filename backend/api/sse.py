"""
Server-Sent Events — a READ-ONLY SUBSCRIBER.

This is the fix for jobs dying on disconnect. The ARQ worker owns job
lifecycle and cleanup; SSE only listens on a Redis pub/sub channel and relays.
Closing a browser tab tears down this generator and NOTHING ELSE.

There is deliberately no cleanup logic in the finally block beyond
unsubscribing from Redis. If you find yourself wanting to cancel a job here,
that belongs in the worker.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from backend.deps import CurrentOrg
from db.cache import get_redis

router = APIRouter(tags=["stream"])

HEARTBEAT_SECONDS = 15


def org_channel(org_id) -> str:
    return f"troy:events:{org_id}"


async def publish(org_id, event_type: str, payload: dict) -> None:
    """Called by the worker. Fire-and-forget; never blocks the pipeline."""
    try:
        await get_redis().publish(
            org_channel(org_id),
            json.dumps(
                {
                    "type": event_type,
                    "at": datetime.now(timezone.utc).isoformat(),
                    "data": payload,
                },
                default=str,
            ),
        )
    except Exception:
        pass


@router.get("/events")
async def events(request: Request, org: CurrentOrg) -> StreamingResponse:
    """
    Event types: job.progress, job.done, job.failed, score.updated,
    alert.fired, capture.started, capture.finished.

    The frontend uses these to invalidate TanStack Query keys — it does not
    build state from the stream, so a missed event degrades to a stale card,
    never to a wrong one.
    """
    redis = get_redis()
    pubsub = redis.pubsub()
    await pubsub.subscribe(org_channel(org.org_id))

    async def gen():
        try:
            yield f"event: connected\ndata: {json.dumps({'org': str(org.org_id)})}\n\n"
            last_beat = asyncio.get_event_loop().time()

            while True:
                if await request.is_disconnected():
                    break

                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
                if msg and msg.get("data"):
                    try:
                        parsed = json.loads(msg["data"])
                        yield f"event: {parsed.get('type', 'message')}\ndata: {msg['data']}\n\n"
                    except json.JSONDecodeError:
                        continue

                now = asyncio.get_event_loop().time()
                if now - last_beat > HEARTBEAT_SECONDS:
                    # Keeps proxies from closing an idle connection.
                    yield ": heartbeat\n\n"
                    last_beat = now
        finally:
            # Unsubscribe ONLY. No job state is touched here, ever.
            await pubsub.unsubscribe(org_channel(org.org_id))
            await pubsub.aclose()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
