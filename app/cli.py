"""Command line for tasks the API can't do for itself, like creating the first admin.

    python -m app.cli create-user alice --role admin
"""

import argparse
import getpass
import sys
from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app import audit
from app.db import Base, SessionLocal
from app.models import Role, User
from app.schemas import UserCreate
from app.security import hash_password

# Not a valid username, so it can never be mistaken for a real account in the audit log.
CLI_ACTOR = "system:cli"


def main(
    argv: list[str] | None = None, session_factory: Callable[[], Session] = SessionLocal
) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    commands = parser.add_subparsers(dest="command", required=True)
    create = commands.add_parser("create-user", help="create a user, such as the first admin")
    create.add_argument("username")
    create.add_argument("--role", choices=[role.value for role in Role], default=Role.VIEWER)
    create.add_argument(
        "--password-stdin",
        action="store_true",
        help="read the password from stdin instead of prompting (for scripts)",
    )
    args = parser.parse_args(argv)

    if args.password_stdin:
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("passwords do not match", file=sys.stderr)
            return 1

    try:
        # The same rules POST /users applies.
        payload = UserCreate(username=args.username, password=password, role=args.role)
    except ValidationError as exc:
        # include_input=False: never echo the password back into the terminal.
        for error in exc.errors(include_input=False, include_url=False):
            print(f"{error['loc'][0]}: {error['msg']}", file=sys.stderr)
        return 1

    with session_factory() as db:
        # The API creates tables on startup, but this may run before it ever has.
        Base.metadata.create_all(db.get_bind())
        user = User(
            username=payload.username,
            password_hash=hash_password(payload.password),
            role=payload.role,
        )
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            print(f"user {payload.username!r} already exists", file=sys.stderr)
            return 1
        audit.record(db, CLI_ACTOR, "user.create", user.id, username=user.username, role=user.role)
        db.commit()

    print(f"created {payload.role} user {payload.username}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
