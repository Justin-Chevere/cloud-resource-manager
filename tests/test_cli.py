import io

from sqlalchemy import select

from app import cli
from app.models import AuditEvent, User


def test_creates_an_admin_who_can_log_in(client, session_factory, monkeypatch):
    monkeypatch.setattr("sys.stdin", io.StringIO("root-password-123\n"))

    argv = ["create-user", "root", "--role", "admin", "--password-stdin"]
    assert cli.main(argv, session_factory) == 0

    login = client.post("/auth/token", data={"username": "root", "password": "root-password-123"})
    assert login.status_code == 200
    with session_factory() as db:
        event = db.scalar(select(AuditEvent))
        assert (event.actor, event.action) == ("system:cli", "user.create")


def test_mismatched_passwords_create_nothing(session_factory, monkeypatch):
    answers = iter(["first-password-123", "second-password-123"])
    monkeypatch.setattr("getpass.getpass", lambda prompt="": next(answers))

    assert cli.main(["create-user", "root"], session_factory) == 1
    with session_factory() as db:
        assert db.scalar(select(User)) is None


def test_invalid_password_is_reported_without_echoing_it(session_factory, monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("tiny-pw\n"))

    assert cli.main(["create-user", "root", "--password-stdin"], session_factory) == 1
    err = capsys.readouterr().err
    assert "password" in err
    assert "tiny-pw" not in err


def test_existing_username_is_reported(session_factory, make_user, monkeypatch, capsys):
    make_user("root")
    monkeypatch.setattr("sys.stdin", io.StringIO("root-password-123\n"))

    assert cli.main(["create-user", "root", "--password-stdin"], session_factory) == 1
    assert "already exists" in capsys.readouterr().err
