from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.auth import OperatorUser, require_role
from app.db import DbSession
from app.models import DesiredState, Resource, Role
from app.schemas import ResourceCreate, ResourceOut, ResourceUpdate

router = APIRouter(
    prefix="/resources",
    tags=["resources"],
    # Deny by default: every route here needs at least a signed-in viewer, and
    # the routes that change things raise that to operator.
    dependencies=[Depends(require_role(Role.VIEWER))],
)


def _get_or_404(db: Session, resource_id: str) -> Resource:
    resource = db.get(Resource, resource_id)
    if resource is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "resource not found")
    return resource


@router.post("", response_model=ResourceOut, status_code=status.HTTP_201_CREATED)
def create_resource(payload: ResourceCreate, db: DbSession, user: OperatorUser) -> Resource:
    resource = Resource(
        name=payload.name,
        image=payload.image,
        desired_state=DesiredState(payload.desired_state),
    )
    db.add(resource)
    try:
        db.flush()  # assigns the id and surfaces a duplicate before anything is audited
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "name already in use") from exc
    audit.record(
        db, user.username, "resource.create", resource.id, name=resource.name, image=resource.image
    )
    db.commit()
    db.refresh(resource)
    return resource


@router.get("", response_model=list[ResourceOut])
def list_resources(db: DbSession) -> list[Resource]:
    return list(db.scalars(select(Resource).order_by(Resource.created_at)))


@router.get("/{resource_id}", response_model=ResourceOut)
def get_resource(resource_id: str, db: DbSession) -> Resource:
    return _get_or_404(db, resource_id)


@router.patch("/{resource_id}", response_model=ResourceOut)
def update_resource(
    resource_id: str, payload: ResourceUpdate, db: DbSession, user: OperatorUser
) -> Resource:
    resource = _get_or_404(db, resource_id)
    if resource.desired_state == DesiredState.DELETED:
        raise HTTPException(status.HTTP_409_CONFLICT, "resource is being deleted")
    new_state = DesiredState(payload.desired_state)
    if new_state != resource.desired_state:
        audit.record(
            db,
            user.username,
            "resource.update",
            resource.id,
            desired_state={"from": resource.desired_state, "to": new_state},
        )
        resource.desired_state = new_state
        db.commit()
        db.refresh(resource)
    return resource


@router.delete("/{resource_id}", response_model=ResourceOut, status_code=status.HTTP_202_ACCEPTED)
def delete_resource(resource_id: str, db: DbSession, user: OperatorUser) -> Resource:
    # 202, not 204: the delete is only requested here. The reconciler tears the
    # container down and then removes the row.
    resource = _get_or_404(db, resource_id)
    if resource.desired_state != DesiredState.DELETED:
        audit.record(db, user.username, "resource.delete", resource.id, name=resource.name)
        resource.desired_state = DesiredState.DELETED
        db.commit()
        db.refresh(resource)
    return resource
