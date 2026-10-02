import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import MetricSample, Resource
from app.runtime import ContainerRuntime

logger = logging.getLogger(__name__)


def collect_once(
    db: Session,
    runtime: ContainerRuntime,
    retention: timedelta,
    now: datetime | None = None,
) -> int:
    """Take one reading of every running resource, then drop readings past retention.

    Returns how many readings were stored.
    """
    now = now or datetime.now(UTC)
    stored = 0
    for resource_id, name in db.execute(select(Resource.id, Resource.name)).all():
        try:
            stats = runtime.stats(name)
        except Exception:
            # One unreadable container shouldn't cost every other resource its reading.
            logger.exception("failed to read stats for %s", name)
            continue
        if stats is None:
            continue
        # Every reading in a pass shares one timestamp, so series line up on a chart.
        db.add(
            MetricSample(
                resource_id=resource_id,
                collected_at=now,
                cpu_percent=stats.cpu_percent,
                memory_bytes=stats.memory_bytes,
            )
        )
        stored += 1
    # Keeps the table from growing forever: old readings simply age out.
    db.execute(delete(MetricSample).where(MetricSample.collected_at < now - retention))
    db.commit()
    return stored


def tick(
    runtime: ContainerRuntime,
    retention: timedelta,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    with session_factory() as db:
        collect_once(db, runtime, retention)


async def run_collector(
    runtime: ContainerRuntime,
    interval: float,
    retention: timedelta,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Collect readings forever. Cancel the task to stop it.

    A loop of its own rather than part of the reconciler, so slow or failing metrics
    can never delay the work of keeping resources in their desired state.
    """
    while True:
        try:
            await asyncio.to_thread(tick, runtime, retention, session_factory)
        except Exception:
            logger.exception("metrics collection failed")
        await asyncio.sleep(interval)
