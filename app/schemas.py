from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActualState, DesiredState, Role

# Users can ask for running or stopped. "deleted" is only reachable via DELETE.
UserDesiredState = Literal["running", "stopped"]

# Length matters more than complexity rules. The cap only bounds hashing work.
Password = Annotated[str, Field(min_length=12, max_length=128)]


class ResourceCreate(BaseModel):
    # Same shape as a Docker container name: lowercase, digits, hyphens.
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$")
    image: str = Field(min_length=1, max_length=255)
    desired_state: UserDesiredState = "running"


class ResourceUpdate(BaseModel):
    desired_state: UserDesiredState


class ResourceOut(BaseModel):
    # from_attributes lets Pydantic read straight from the SQLAlchemy object.
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    image: str
    desired_state: DesiredState
    actual_state: ActualState
    created_at: datetime
    updated_at: datetime


class MetricPoint(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    collected_at: datetime
    cpu_percent: float  # percent of one CPU core
    memory_bytes: int


class LatestMetric(MetricPoint):
    resource_id: str
    name: str


class Token(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int  # seconds


class UserCreate(BaseModel):
    username: str = Field(pattern=r"^[a-z0-9][a-z0-9_.-]{2,31}$")
    password: Password
    role: Role = Role.VIEWER


class UserUpdate(BaseModel):
    role: Role | None = None
    is_active: bool | None = None


class UserOut(BaseModel):
    # No password_hash here: it never leaves the server.
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    role: Role
    is_active: bool
    created_at: datetime


class PasswordResetIssued(BaseModel):
    token: str
    expires_at: datetime


class PasswordResetComplete(BaseModel):
    token: str = Field(min_length=1, max_length=128)
    new_password: Password


class AuditEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    actor: str
    action: str
    target_id: str
    details: dict[str, Any]
