from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models import ActualState, DesiredState

# Users can ask for running or stopped. "deleted" is only reachable via DELETE.
UserDesiredState = Literal["running", "stopped"]


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
