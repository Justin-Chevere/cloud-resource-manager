import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DesiredState(enum.StrEnum):
    """What the user asked for. Only the API writes this."""

    RUNNING = "running"
    STOPPED = "stopped"
    DELETED = "deleted"


class ActualState(enum.StrEnum):
    """What is really happening. Only the reconciler writes this."""

    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class Role(enum.StrEnum):
    """Least to most access. Each role can do everything the ones before it can."""

    VIEWER = "viewer"  # read resources
    OPERATOR = "operator"  # + create, start, stop, delete resources
    ADMIN = "admin"  # + manage users, read the audit log


def _enum_column(enum_cls: type[enum.StrEnum]) -> Enum:
    # Store "running" rather than "RUNNING" so the DB values match the API values.
    return Enum(
        enum_cls,
        values_callable=lambda e: [m.value for m in e],
        native_enum=False,
        length=16,
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _new_id() -> str:
    return str(uuid.uuid4())


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    name: Mapped[str] = mapped_column(String(63), unique=True, index=True)
    image: Mapped[str] = mapped_column(String(255))
    desired_state: Mapped[DesiredState] = mapped_column(
        _enum_column(DesiredState), default=DesiredState.RUNNING
    )
    actual_state: Mapped[ActualState] = mapped_column(
        _enum_column(ActualState), default=ActualState.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum_column(Role), default=Role.VIEWER)
    # Users are deactivated rather than deleted: their tokens stop working at
    # once, and the history of what they did stays intact.
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    # A username snapshot rather than a foreign key, so each record reads the
    # same forever, whatever happens to the user afterwards.
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
