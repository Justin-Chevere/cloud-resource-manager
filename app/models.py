import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Index, String
from sqlalchemy.engine import Dialect
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

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


class UTCDateTime(TypeDecorator[datetime]):
    """A datetime column that always comes back timezone-aware UTC, on every database.

    SQLite has no time zones and returns naive datetimes. The API would send those
    without a "Z", and a browser would read them as local time, shifting every point
    on a chart. So values are stored as UTC and marked UTC on the way back out.
    Naive values are refused rather than guessed at.
    """

    impl = DateTime
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise TypeError("naive datetime: use a timezone-aware one, e.g. datetime.now(UTC)")
        return value.astimezone(UTC).replace(tzinfo=None)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        return value.replace(tzinfo=UTC) if value is not None else None


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
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now, onupdate=_now)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_id)
    username: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(_enum_column(Role), default=Role.VIEWER)
    # Users are deactivated rather than deleted: their tokens stop working at
    # once, and the history of what they did stays intact.
    is_active: Mapped[bool] = mapped_column(default=True)
    # Copied into every token. A password reset bumps it, which retires all
    # tokens issued before the reset.
    token_version: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)


class PasswordReset(Base):
    """The one outstanding password-reset token for a user, if there is one."""

    __tablename__ = "password_resets"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), primary_key=True)
    # Only a hash. The token itself is shown once and never stored, so a leaked
    # database can't be used to reset anyone's password.
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime)


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=_now)
    # A username snapshot rather than a foreign key, so each record reads the
    # same forever, whatever happens to the user afterwards.
    actor: Mapped[str] = mapped_column(String(32))
    action: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[str] = mapped_column(String(36), index=True)
    details: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)


class MetricSample(Base):
    """One CPU and memory reading of one resource."""

    __tablename__ = "metric_samples"
    # Matches the two questions asked of this table: one resource over a time
    # range, and the newest reading of each resource.
    __table_args__ = (Index("ix_metric_samples_resource_time", "resource_id", "collected_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # Not a foreign key: like a series in Prometheus, a deleted resource's
    # readings simply stop arriving and age out with the retention window.
    resource_id: Mapped[str] = mapped_column(String(36))
    # Indexed on its own as well, for the retention cleanup ("older than X").
    collected_at: Mapped[datetime] = mapped_column(UTCDateTime, index=True)
    cpu_percent: Mapped[float]
    # 64-bit: 2 GiB of memory would already overflow a 32-bit integer.
    memory_bytes: Mapped[int] = mapped_column(BigInteger)
