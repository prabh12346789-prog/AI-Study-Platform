from __future__ import annotations

import asyncio
import logging
import sys
from datetime import datetime, timezone

from src.core.config import settings
from src.current_affairs.ingestion_service import OfficialCurrentAffairsIngestionService

log = logging.getLogger(__name__)

_SCHEDULER_TASK: asyncio.Task | None = None


async def _run_scheduler_loop():
    svc = OfficialCurrentAffairsIngestionService()
    interval_seconds = settings.CURRENT_AFFAIRS_INTERVAL_HOURS * 3600

    # Startup check
    if not settings.CURRENT_AFFAIRS_AUTO_INGEST:
        log.info("Automatic Current Affairs ingestion is disabled (CURRENT_AFFAIRS_AUTO_INGEST=false)")
        return

    last_run = svc.get_last_successful_run()
    stale = True
    if last_run and last_run.completed_at:
        age_hours = (datetime.now(timezone.utc) - last_run.completed_at.replace(tzinfo=timezone.utc)).total_seconds() / 3600
        if age_hours < settings.CURRENT_AFFAIRS_STARTUP_MAX_AGE_HOURS:
            stale = False
            log.info("Current Affairs data is fresh (last run %.1f hours ago)", age_hours)

    if stale:
        log.info("Triggering background startup ingestion run...")
        try:
            res = await svc.run_ingestion(trigger_type="startup")
            log.info("Startup ingestion completed: %s", res.get("status"))
        except Exception as exc:
            log.error("Startup ingestion failed: %s", exc)

    # Recurring loop
    while True:
        try:
            await asyncio.sleep(interval_seconds)
            log.info("Triggering scheduled Current Affairs ingestion run...")
            res = await svc.run_ingestion(trigger_type="scheduler")
            log.info("Scheduled ingestion completed: %s", res.get("status"))
        except asyncio.CancelledError:
            log.info("Current Affairs scheduler loop cancelled")
            break
        except Exception as exc:
            log.error("Scheduled ingestion loop error: %s", exc)


def start_scheduler():
    global _SCHEDULER_TASK
    # Do not run scheduler under pytest or if auto ingest is disabled
    if "pytest" in sys.modules or not settings.CURRENT_AFFAIRS_AUTO_INGEST:
        return

    if _SCHEDULER_TASK is None or _SCHEDULER_TASK.done():
        _SCHEDULER_TASK = asyncio.create_task(_run_scheduler_loop())
        log.info("Current Affairs background scheduler started")


def stop_scheduler():
    global _SCHEDULER_TASK
    if _SCHEDULER_TASK and not _SCHEDULER_TASK.done():
        _SCHEDULER_TASK.cancel()
        log.info("Current Affairs background scheduler stopped")
    _SCHEDULER_TASK = None
