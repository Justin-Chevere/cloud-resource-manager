from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import get_settings

ALGORITHM = "HS256"

# Argon2id with the library defaults (64 MiB of memory, 3 passes). Slow and
# memory-hungry on purpose: cheap for one login, very expensive for an attacker
# trying billions of guesses against a stolen database.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    # The result embeds a random salt and the parameters used, so two users
    # with the same password still get different hashes.
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: str, expires_in: timedelta | None = None) -> str:
    settings = get_settings()
    if expires_in is None:
        expires_in = timedelta(minutes=settings.access_token_minutes)
    now = datetime.now(UTC)
    claims = {"sub": user_id, "iat": now, "exp": now + expires_in}
    return jwt.encode(claims, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> str | None:
    """Return the user id a valid, unexpired token was issued for, or None."""
    try:
        claims = jwt.decode(
            token,
            get_settings().jwt_secret,
            # Pinned, never taken from the token's own header: letting the token
            # pick is how forged "alg": "none" tokens get accepted.
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub"]},
        )
    except jwt.InvalidTokenError:
        return None
    return claims["sub"]
