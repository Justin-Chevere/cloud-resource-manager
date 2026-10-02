from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.auth import AdminUser, require_role
from app.config import get_settings
from app.db import DbSession
from app.models import PasswordReset, Role, User
from app.schemas import PasswordResetIssued, UserCreate, UserOut, UserUpdate
from app.security import hash_password, new_reset_token

router = APIRouter(
    prefix="/users",
    tags=["users"],
    dependencies=[Depends(require_role(Role.ADMIN))],
)


def _get_or_404(db: Session, user_id: str) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return user


def _active_admin_count(db: Session) -> int:
    query = select(func.count()).where(User.role == Role.ADMIN, User.is_active.is_(True))
    return db.scalar(query) or 0


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: DbSession, admin: AdminUser) -> User:
    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    try:
        db.flush()  # assigns the id and surfaces a duplicate before anything is audited
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "username already in use") from exc
    audit.record(db, admin.username, "user.create", user.id, username=user.username, role=user.role)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UserOut])
def list_users(db: DbSession) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at)))


@router.patch("/{user_id}", response_model=UserOut)
def update_user(user_id: str, payload: UserUpdate, db: DbSession, admin: AdminUser) -> User:
    user = _get_or_404(db, user_id)
    changes = payload.model_dump(exclude_unset=True, exclude_none=True)

    stays_admin = changes.get("role", user.role) == Role.ADMIN and changes.get(
        "is_active", user.is_active
    )
    if user.role == Role.ADMIN and user.is_active and not stays_admin:
        # Without an active admin, nobody could manage users through the API again.
        if _active_admin_count(db) == 1:
            raise HTTPException(status.HTTP_409_CONFLICT, "cannot remove the last active admin")

    details = {}
    for field, new in changes.items():
        old = getattr(user, field)
        if new != old:
            details[field] = {"from": old, "to": new}
            setattr(user, field, new)
    if details:
        audit.record(db, admin.username, "user.update", user.id, **details)
        db.commit()
        db.refresh(user)
    return user


@router.post(
    "/{user_id}/password-reset",
    response_model=PasswordResetIssued,
    status_code=status.HTTP_201_CREATED,
)
def issue_password_reset(user_id: str, db: DbSession, admin: AdminUser) -> PasswordResetIssued:
    """Issue a one-time token the user can set a new password with.

    Hand it to the user directly. The admin never learns the new password, and
    the token is shown only in this response.
    """
    user = _get_or_404(db, user_id)
    token, token_hash = new_reset_token()
    expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().password_reset_minutes)
    # Only the newest token works: issuing one cancels any earlier one.
    db.execute(delete(PasswordReset).where(PasswordReset.user_id == user.id))
    db.add(PasswordReset(user_id=user.id, token_hash=token_hash, expires_at=expires_at))
    audit.record(db, admin.username, "password_reset.issue", user.id)
    db.commit()
    return PasswordResetIssued(token=token, expires_at=expires_at)
