from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select

from app.auth import require_role
from app.db import DbSession
from app.models import AuditEvent, Role
from app.schemas import AuditEventOut

router = APIRouter(
    prefix="/audit",
    tags=["audit"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


@router.get("", response_model=list[AuditEventOut])
def list_audit_events(
    db: DbSession, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[AuditEvent]:
    """Most recent first."""
    return list(db.scalars(select(AuditEvent).order_by(AuditEvent.id.desc()).limit(limit)))
