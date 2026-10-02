from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import delete

from app import audit
from app.auth import CurrentUser, LoginGuardDep, authenticate
from app.config import get_settings
from app.db import DbSession
from app.models import PasswordReset, User
from app.schemas import PasswordResetComplete, Token, UserOut
from app.security import create_access_token, hash_password, hash_reset_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    request: Request,
    db: DbSession,
    guard: LoginGuardDep,
) -> Token:
    """Exchange a username and password for a bearer token (OAuth2 password flow)."""
    # Behind a proxy, run uvicorn with --proxy-headers so this is the real client.
    client = request.client.host if request.client else "unknown"
    retry_after = guard.retry_after(form.username, client)
    if retry_after:
        # Answered before the password is checked, so a blocked attacker learns
        # nothing from more guesses, not even when one of them is right.
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "too many failed logins, try again later",
            headers={"Retry-After": str(retry_after)},
        )

    user = authenticate(db, form.username, form.password)
    if user is None:
        guard.record_failure(form.username, client)
        # One message for every failure, so it never confirms that a username exists.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    # Only the account's count is cleared. Clearing the client's too would let an
    # attacker reset their own count by logging into an account they control.
    guard.clear_account(form.username)
    return Token(
        access_token=create_access_token(user),
        expires_in=get_settings().access_token_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user


@router.post("/password-reset", status_code=status.HTTP_204_NO_CONTENT)
def complete_password_reset(
    payload: PasswordResetComplete, db: DbSession, guard: LoginGuardDep
) -> None:
    """Set a new password with a one-time token from an admin.

    Public on purpose: whoever needs this can't log in.
    """
    # Deleting the row is what claims the token: if two requests race with the
    # same token, only one of them can delete it, so a token works exactly once.
    user_id = db.scalar(
        delete(PasswordReset)
        .where(
            PasswordReset.token_hash == hash_reset_token(payload.token),
            PasswordReset.expires_at > datetime.now(UTC),
        )
        .returning(PasswordReset.user_id)
    )
    user = db.get(User, user_id) if user_id is not None else None
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid or expired reset token")

    user.password_hash = hash_password(payload.new_password)
    # Retires every token issued before now: a session someone else may hold
    # ends together with the old password.
    user.token_version += 1
    audit.record(db, user.username, "password_reset.complete", user.id)
    db.commit()
    guard.clear_account(user.username)
