from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DesiredState, Resource
from app.schemas import ResourceCreate, ResourceOut, ResourceUpdate

router = APIRouter(prefix="/resources", tags=["resources"])

DbSession = Annotated[Session, Depends(get_db)]


def _get_or_404(db: Session, resource_id: str) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "resource not found")
    return resource


@router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, db: DbSession) -> Resource:
    resource = Resource(
        name=payload.name,
        image=payload.image,
        desired_state=DesiredState(payload.desired_state),
    )
    db.add(resource)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "name already in use") from exc
    db.refresh(resource)
    return resource


@router.get("", response_model=list[ResourceOut])
def list_resources(db: DbSession) -> list[Resource]:
    return list(db.scalars(select(Resource).order_by(Resource.created_at)))


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: str, db: DbSession) -> Resource:
    return _get_or_404(db, resource_id)


@router.patch("/{resource_id}", response_model=ResourceOut)
def update_resource(resource_id: str, payload: ResourceUpdate, db: DbSession) -> Resource:
    resource = _get_or_404(db, resource_id)
    if resource.desired_state == DesiredState.DELETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "resource is being deleted")
    resource.desired_state = DesiredState(payload.desired_state)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/{resource_id}", response_model=ResourceOut, status_code=status.HTTP_202_ACCEPTED)
def delete_resource(resource_id: str, db: DbSession) -> Resource:
    # 202, not 204: the delete is only requested here. The reconciler tears the
    # container down and then removes the row.
    resource = _get_or_404(db, resource_id)
    resource.desired_state = DesiredState.DELETED
    db.commit()
    db.refresh(resource)
    return resource
