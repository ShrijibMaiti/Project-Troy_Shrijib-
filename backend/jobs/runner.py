"""
ARQ worker — durable, disconnect-safe.

The fix for "job state can't survive a disconnect": job lifecycle lives HERE,
in a Redis-backed worker, not in an HTTP request or an SSE generator's finally
block. A client can disconnect, reconnect, or never connect at all; the job
runs regardless.

Start with:  arq backend.jobs.runner.WorkerSettings
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from arq import create_pool
from arq.connections import RedisSettings

from backend.config import settings
from backend.jobs import tasks

_pool = None


def redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.redis_url)


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await create_pool(redis_settings())
    return _pool


async def enqueue(task_name: str, *args, **kwargs) -> str:
    """
    Queue a job and return its id immediately. Endpoints never await the work.
    """
    pool = await get_pool()
    job = await pool.enqueue_job(task_name, *args, **kwargs)
    return job.job_id if job else str(uuid.uuid4())


async def job_status(job_id: str) -> dict:
    from arq.jobs import Job

    pool = await get_pool()
    job = Job(job_id, pool)
    try:
        info = await job.info()
        st = await job.status()
        return {
            "job_id": job_id,
            "status": str(st),
            "enqueued_at": info.enqueue_time.isoformat() if info else None,
            "detail": {"function": info.function if info else None},
        }
    except Exception:
        return {"job_id": job_id, "status": "unknown", "detail": {}}


async def on_startup(ctx: dict) -> None:
    ctx["started_at"] = datetime.now(timezone.utc)
    print(f"[worker] up at {ctx['started_at'].isoformat()}")
    for w in settings.validate_runtime():
        print(f"[worker] WARNING: {w}")


async def on_shutdown(ctx: dict) -> None:
    from db.cache import close_redis
    from db.session import dispose_engine

    await dispose_engine()
    await close_redis()
    print("[worker] down")


class WorkerSettings:
    functions = [
        tasks.run_capture,
        tasks.capture_vendor,
        tasks.recompute_score,
        tasks.generate_narrative,
        tasks.export_register,
        tasks.verify_chain_job,
    ]
    on_startup = on_startup
    on_shutdown = on_shutdown
    redis_settings = redis_settings()
    max_jobs = settings.capture_concurrency
    job_timeout = settings.job_timeout_seconds
    keep_result = 3600
    # Retries are bounded: a source that fails three times is a source
    # problem, and burning quota on it hurts every other vendor in the run.
    max_tries = 3