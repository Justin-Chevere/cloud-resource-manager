from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from app.auth import require_role
from app.db import DbSession
from app.models import MetricSample, Resource, Role
from app.schemas import LatestMetric

router = APIRouter(
    prefix="/metrics",
    tags=["metrics"],
    dependencies=[Depends(require_role(Role.VIEWER))],
)


@router.get("/latest", response_model=list[LatestMetric])
def latest_metrics(db: DbSession) -> list[LatestMetric]:
    """The newest reading of each resource, for an overview screen.

    A stopped resource keeps its last reading, so check `collected_at` for staleness.
    """
    newest = (
        select(MetricSample.resource_id, func.max(MetricSample.collected_at).label("collected_at"))
        .group_by(MetricSample.resource_id)
        .subquery()
    )
    query = (
        select(
            Resource.id.label("resource_id"),
            Resource.name,
            MetricSample.collected_at,
            MetricSample.cpu_percent,
            MetricSample.memory_bytes,
        )
        .join(newest, newest.c.resource_id == Resource.id)
        .join(
            MetricSample,
            (MetricSample.resource_id == newest.c.resource_id)
            & (MetricSample.collected_at == newest.c.collected_at),
        )
        .order_by(Resource.name)
    )
    return [LatestMetric.model_validate(row) for row in db.execute(query)]
