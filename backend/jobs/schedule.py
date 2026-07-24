"""
APScheduler — the 07:00 UTC daily capture.

The scheduler only ENQUEUES. It never executes work in-process: if the API
container restarts mid-capture, the queued jobs survive in Redis.

Run as its own process, or in the API container with SCHEDULER_ENABLED=1.
Exactly one instance must run, or every vendor gets captured twice.
"""

from __future__ import annotations

import asyncio
import os

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.config import settings

scheduler: AsyncIOScheduler | None = None


async def _enqueue_daily_capture() -> None:
    from backend.jobs.runner import enqueue

    job_id = await enqueue("run_capture")
    print(f"[scheduler] daily capture queued: {job_id}")


async def _enqueue_chain_verify() -> None:
    from backend.jobs.runner import enqueue

    await enqueue("verify_chain_job")


def start_scheduler() -> AsyncIOScheduler:
    global scheduler
    if scheduler is not None:
        return scheduler

    scheduler = AsyncIOScheduler(timezone="UTC")

    scheduler.add_job(
        _enqueue_daily_capture,
        CronTrigger(
            hour=settings.capture_cron_hour,
            minute=settings.capture_cron_minute,
            timezone="UTC",
        ),
        id="daily_capture",
        replace_existing=True,
        misfire_grace_time=3600,  # a late run beats a skipped day
    )

    # Nightly integrity check, offset from capture.
    scheduler.add_job(
        _enqueue_chain_verify,
        CronTrigger(hour=3, minute=30, timezone="UTC"),
        id="chain_verify",
        replace_existing=True,
        misfire_grace_time=3600,
    )

    scheduler.start()
    print(
        f"[scheduler] started — capture at "
        f"{settings.capture_cron_hour:02d}:{settings.capture_cron_minute:02d} UTC"
    )
    return scheduler


def shutdown_scheduler() -> None:
    global scheduler
    if scheduler is not None:
        scheduler.shutdown(wait=False)
        scheduler = None


def is_enabled() -> bool:
    return os.getenv("SCHEDULER_ENABLED", "0") == "1"


if __name__ == "__main__":
    start_scheduler()
    asyncio.get_event_loop().run_forever()