from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditEvent


def record(db: Session, actor: str, action: str, target_id: str, **details: Any) -> None:
    """Stage an audit event in the caller's transaction.

    It commits together with the change it describes, so a change is never saved
    without its record, and a change that fails leaves no record behind.
    """
    db.add(AuditEvent(actor=actor, action=action, target_id=target_id, details=details))
