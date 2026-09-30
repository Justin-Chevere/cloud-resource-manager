from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth import CurrentUser, authenticate
from app.config import get_settings
from app.db import DbSession
from app.models import User
from app.schemas import Token, UserOut
from app.security import create_access_token

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/token", response_model=Token)
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession) -> Token:
    """Exchange a username and password for a bearer token (OAuth2 password flow)."""
    user = authenticate(db, form.username, form.password)
    if user is None:
        # One message for every failure, so it never confirms that a username exists.
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return Token(
        access_token=create_access_token(user.id),
        expires_in=get_settings().access_token_minutes * 60,
    )


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> User:
    return user
