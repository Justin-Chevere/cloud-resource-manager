import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum, String
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


class Resource(Base):
    __tablename__ = "resources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
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
