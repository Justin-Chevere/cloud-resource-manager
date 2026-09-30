import asyncio
import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.models import ActualState, DesiredState, Resource
from app.runtime import ContainerRuntime, ObservedState

logger = logging.getLogger(__name__)


def reconcile_once(db: Session, runtime: ContainerRuntime) -> None:
    """One pass over every resource: compare desired to observed, act on the difference."""
    # Ids first, then one fetch each: a resource that disappears mid-pass is skipped
    # rather than crashing the pass, and each commit below only touches one resource.
    for resource_id in db.scalars(select(Resource.id)).all():
        resource = db.get(Resource, resource_id)
        if resource is None:
            continue
        name = resource.name
        try:
            _reconcile(db, runtime, resource)
        except Exception:
            logger.exception("failed to reconcile %s", name)
            db.rollback()
            failed = db.get(Resource, resource_id)
            if failed is not None:
                failed.actual_state = ActualState.ERROR
        db.commit()


def _reconcile(db: Session, runtime: ContainerRuntime, resource: Resource) -> None:
    name = resource.name
    desired = resource.desired_state
    observed = runtime.status(name)

    if desired == DesiredState.DELETED:
        if observed != ObservedState.MISSING:
            runtime.remove(name)
            logger.info("removed %s", name)
        db.delete(resource)
        return

    if desired == DesiredState.RUNNING and observed != ObservedState.RUNNING:
        runtime.start(name, resource.image)
        logger.info("started %s", name)
    elif desired == DesiredState.STOPPED and observed == ObservedState.RUNNING:
        runtime.stop(name)
        logger.info("stopped %s", name)

    # Record what the runtime reports now, not what we hoped the call achieved.
    if runtime.status(name) == ObservedState.RUNNING:
        resource.actual_state = ActualState.RUNNING
    else:
        resource.actual_state = ActualState.STOPPED


def tick(
    runtime: ContainerRuntime,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    with session_factory() as db:
        reconcile_once(db, runtime)


async def run_reconciler(
    runtime: ContainerRuntime,
    interval: float,
    session_factory: Callable[[], Session] = SessionLocal,
) -> None:
    """Run reconcile passes forever. Cancel the task to stop it."""
    while True:
        try:
            # The runtime and database calls block, so keep them off the event loop.
            await asyncio.to_thread(tick, runtime, session_factory)
        except Exception:
            logger.exception("reconcile pass failed")
        await asyncio.sleep(interval)
