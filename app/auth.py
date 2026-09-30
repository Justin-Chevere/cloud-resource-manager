from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import DbSession
from app.models import Role, User
from app.security import decode_access_token, hash_password, verify_password

# Reads "Authorization: Bearer <token>" and answers 401 if it is missing. The
# tokenUrl also wires up the Authorize button in the /docs page.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

_ROLE_RANK = {Role.VIEWER: 0, Role.OPERATOR: 1, Role.ADMIN: 2}

# Checked against when the username doesn't exist, so that case takes as long as
# a wrong password. Otherwise response times would reveal which usernames exist.
_DUMMY_HASH = hash_password("not-a-real-password")


def authenticate(db: Session, username: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        verify_password(password, _DUMMY_HASH)
        return None
    if not verify_password(password, user.password_hash) or not user.is_active:
        return None
    return user


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)], db: DbSession) -> User:
    user_id = decode_access_token(token)
    # The token only says who you are. The user and role are loaded fresh on every
    # request, so deactivations and role changes apply even to tokens already issued.
    user = db.get(User, user_id) if user_id is not None else None
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(minimum: Role) -> Callable[[User], User]:
    def check(user: Annotated[User, Depends(get_current_user)]) -> User:
        if _ROLE_RANK[user.role] < _ROLE_RANK[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires the {minimum} role")
        return user

    return check


CurrentUser = Annotated[User, Depends(get_current_user)]
# "At least this role": an admin passes an operator check.
OperatorUser = Annotated[User, Depends(require_role(Role.OPERATOR))]
AdminUser = Annotated[User, Depends(require_role(Role.ADMIN))]
