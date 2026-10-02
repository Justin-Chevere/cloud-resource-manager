import re
from datetime import UTC, datetime, timedelta

import jwt

from app.main import app
from app.models import Role
from app.security import create_access_token

# Every other route must turn away a caller without a token. Adding a route
# here is a deliberate decision to make it public.
PUBLIC_ROUTES = {
    ("GET", "/health"),
    ("POST", "/auth/token"),
    ("POST", "/auth/password-reset"),
}


def _login(client, username, password):
    return client.post("/auth/token", data={"username": username, "password": password})


def _bearer(token):
    return {"Authorization": f"Bearer {token}"}


def _claims(user):
    # Every claim a real token has, so a forgery fails only on its signature.
    expires = datetime.now(UTC) + timedelta(minutes=5)
    return {"sub": user.id, "ver": user.token_version, "exp": expires}


def test_login_returns_a_token_that_identifies_the_user(client, make_user):
    make_user("alice", Role.OPERATOR, password="alice-password-123")

    response = _login(client, "alice", "alice-password-123")
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 30 * 60

    me = client.get("/auth/me", headers=_bearer(body["access_token"]))
    assert me.status_code == 200
    assert me.json()["username"] == "alice"
    assert me.json()["role"] == "operator"


def test_wrong_password_and_unknown_user_get_the_same_answer(client, make_user):
    make_user("alice", password="alice-password-123")

    wrong_password = _login(client, "alice", "not-the-password")
    unknown_user = _login(client, "mallory", "alice-password-123")

    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()


def test_deactivated_user_cannot_log_in(client, make_user):
    make_user("alice", password="alice-password-123", is_active=False)
    assert _login(client, "alice", "alice-password-123").status_code == 401


def test_every_non_public_route_rejects_anonymous_requests(client):
    # The OpenAPI schema is the public list of every endpoint the app serves.
    checked = []
    for route_path, operations in app.openapi()["paths"].items():
        for method in operations:
            if (method.upper(), route_path) in PUBLIC_ROUTES:
                continue
            path = re.sub(r"\{[^}]+\}", "x", route_path)
            response = client.request(method, path)
            assert response.status_code == 401, f"{method} {route_path} answered anonymously"
            checked.append((method, route_path))
    # Guards against the loop silently finding nothing and passing vacuously.
    assert len(checked) >= 10


def test_garbage_token_is_rejected(client):
    assert client.get("/auth/me", headers=_bearer("not-a-jwt")).status_code == 401


def test_expired_token_is_rejected(client, make_user):
    user = make_user("alice")
    token = create_access_token(user, expires_in=timedelta(seconds=-1))
    assert client.get("/auth/me", headers=_bearer(token)).status_code == 401


def test_token_signed_with_another_secret_is_rejected(client, make_user):
    user = make_user("alice")
    forged = jwt.encode(
        _claims(user), "an-attacker-chosen-secret-that-is-long-enough", algorithm="HS256"
    )
    assert client.get("/auth/me", headers=_bearer(forged)).status_code == 401


def test_unsigned_token_is_rejected(client, make_user):
    # The classic JWT forgery: declare "alg": "none" and send no signature at all.
    user = make_user("alice")
    forged = jwt.encode(_claims(user), None, algorithm="none")
    assert client.get("/auth/me", headers=_bearer(forged)).status_code == 401


def test_viewer_can_read_resources_but_not_change_them(viewer_client, operator_client):
    created = operator_client.post("/resources", json={"name": "web-1", "image": "nginx"}).json()
    path = f"/resources/{created['id']}"

    assert viewer_client.get("/resources").status_code == 200
    assert viewer_client.get(path).status_code == 200
    assert viewer_client.post("/resources", json={"name": "web-2", "image": "x"}).status_code == 403
    assert viewer_client.patch(path, json={"desired_state": "stopped"}).status_code == 403
    assert viewer_client.delete(path).status_code == 403


def test_only_admins_manage_users_and_read_the_audit_log(operator_client, admin_client):
    for path in ("/users", "/audit"):
        assert operator_client.get(path).status_code == 403
        assert admin_client.get(path).status_code == 200


def test_admin_can_do_what_an_operator_can(admin_client):
    response = admin_client.post("/resources", json={"name": "web-1", "image": "nginx"})
    assert response.status_code == 201


def test_deactivation_revokes_tokens_already_issued(admin_client, viewer_client):
    assert viewer_client.get("/resources").status_code == 200

    user_id = viewer_client.get("/auth/me").json()["id"]
    admin_client.patch(f"/users/{user_id}", json={"is_active": False})

    assert viewer_client.get("/resources").status_code == 401


def test_role_changes_apply_to_tokens_already_issued(admin_client, viewer_client):
    resource = {"name": "web-1", "image": "nginx"}
    assert viewer_client.post("/resources", json=resource).status_code == 403

    user_id = viewer_client.get("/auth/me").json()["id"]
    admin_client.patch(f"/users/{user_id}", json={"role": "operator"})

    assert viewer_client.post("/resources", json=resource).status_code == 201
