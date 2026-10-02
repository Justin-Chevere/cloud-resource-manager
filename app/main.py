import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from datetime import timedelta

from fastapi import FastAPI

from app import models  # noqa: F401  (registers the tables on Base.metadata)
from app.config import get_settings
from app.db import Base, engine
from app.metrics import run_collector
from app.reconciler import run_reconciler
from app.routers import audit, auth, health, metrics, resources, users
from app.runtime import build_runtime

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logging.basicConfig(level=logging.INFO)
    settings = get_settings()
    if "jwt_secret" not in settings.model_fields_set:
        logger.warning("JWT_SECRET is not set: using a random secret, so logins reset on restart")
    # Fine while the schema is tiny. Replace with Alembic migrations later.
    Base.metadata.create_all(engine)

    loops = []
    if settings.reconciler_enabled or settings.metrics_enabled:
        app.state.runtime = build_runtime(settings)
    if settings.reconciler_enabled:
        loops.append(run_reconciler(app.state.runtime, settings.reconcile_interval_seconds))
    if settings.metrics_enabled:
        retention = timedelta(hours=settings.metrics_retention_hours)
        loops.append(
            run_collector(app.state.runtime, settings.metrics_interval_seconds, retention)
        )
    tasks = [asyncio.create_task(loop) for loop in loops]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task


def create_app() -> FastAPI:
    app = FastAPI(title=get_settings().app_name, lifespan=lifespan)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(resources.router)
    app.include_router(metrics.router)
    app.include_router(users.router)
    app.include_router(audit.router)
    return app


app = create_app()
