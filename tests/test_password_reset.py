from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update

from app.models import PasswordReset
from app.security import hash_reset_token

PASSWORD = "bob-password-123"
NEW_PASSWORD = "bob-new-password-456"


@pytest.fixture
def bob(make_user):
    return make_user("bob", password=PASSWORD)


def _login(client, password):
    return client.post("/auth/token", data={"username": "bob", "password": password})


def _issue(admin_client, user_id):
    return admin_client.post(f"/users/{user_id}/password-reset")


def _reset(client, token, new_password=NEW_PASSWORD):
    return client.post("/auth/password-reset", json={"token": token, "new_password": new_password})


def test_reset_replaces_the_password(admin_client, client, bob):
    issued = _issue(admin_client, bob.id)
    assert issued.status_code == 201

    assert _reset(client, issued.json()["token"]).status_code == 204

    assert _login(client, PASSWORD).status_code == 401
    assert _login(client, NEW_PASSWORD).status_code == 200


def test_token_works_only_once(admin_client, client, bob):
    token = _issue(admin_client, bob.id).json()["token"]
    assert _reset(client, token).status_code == 204
    assert _reset(client, token, "another-password-789").status_code == 400


def test_expired_token_is_rejected(admin_client, client, bob, session_factory):
    token = _issue(admin_client, bob.id).json()["token"]
    with session_factory() as db:
        expired = datetime.now(UTC) - timedelta(minutes=1)
        db.execute(update(PasswordReset).values(expires_at=expired))
        db.commit()

    assert _reset(client, token).status_code == 400


def test_issuing_a_new_token_cancels_the_previous_one(admin_client, client, bob):
    first = _issue(admin_client, bob.id).json()["token"]
    second = _issue(admin_client, bob.id).json()["token"]

    assert _reset(client, first).status_code == 400
    assert _reset(client, second).status_code == 204


def test_made_up_token_is_rejected(client, bob):
    assert _reset(client, "not-a-real-token").status_code == 400


def test_weak_new_password_is_rejected_without_using_up_the_token(admin_client, client, bob):
    token = _issue(admin_client, bob.id).json()["token"]
    assert _reset(client, token, "short").status_code == 422
    assert _reset(client, token).status_code == 204


def test_reset_ends_sessions_started_before_it(admin_client, client, bob):
    old = {"Authorization": f"Bearer {_login(client, PASSWORD).json()['access_token']}"}
    assert client.get("/auth/me", headers=old).status_code == 200

    _reset(client, _issue(admin_client, bob.id).json()["token"])

    assert client.get("/auth/me", headers=old).status_code == 401
    new = {"Authorization": f"Bearer {_login(client, NEW_PASSWORD).json()['access_token']}"}
    assert client.get("/auth/me", headers=new).status_code == 200


def test_reset_lifts_a_login_pause(admin_client, client, bob):
    statuses = [_login(client, "wrong-password").status_code for _ in range(10)]
    assert statuses[-1] == 429

    _reset(client, _issue(admin_client, bob.id).json()["token"])

    assert _login(client, NEW_PASSWORD).status_code == 200


def test_only_admins_can_issue_resets(operator_client, bob):
    assert operator_client.post(f"/users/{bob.id}/password-reset").status_code == 403


def test_issuing_for_an_unknown_user_is_404(admin_client):
    assert _issue(admin_client, "nope").status_code == 404


def test_token_is_stored_only_as_a_hash(admin_client, bob, session_factory):
    token = _issue(admin_client, bob.id).json()["token"]
    with session_factory() as db:
        stored = db.scalar(select(PasswordReset))

    assert stored.token_hash != token
    assert stored.token_hash == hash_reset_token(token)


def test_reset_is_audited_without_the_token(admin_client, client, bob):
    token = _issue(admin_client, bob.id).json()["token"]
    _reset(client, token)

    events = admin_client.get("/audit").json()

    assert [(e["action"], e["actor"]) for e in events] == [
        ("password_reset.complete", "bob"),
        ("password_reset.issue", "admin"),
    ]
    assert token not in str(events)
