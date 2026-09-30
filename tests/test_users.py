NEW_USER = {"username": "bob", "password": "bob-password-123", "role": "viewer"}


def test_admin_creates_a_user_who_can_log_in(admin_client, client):
    response = admin_client.post("/users", json=NEW_USER)
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "bob"
    assert body["role"] == "viewer"
    assert "password" not in body
    assert "password_hash" not in body

    login = client.post("/auth/token", data={"username": "bob", "password": "bob-password-123"})
    assert login.status_code == 200


def test_duplicate_username_is_conflict(admin_client):
    admin_client.post("/users", json=NEW_USER)
    assert admin_client.post("/users", json=NEW_USER).status_code == 409


def test_short_password_and_bad_username_are_rejected(admin_client):
    assert admin_client.post("/users", json={**NEW_USER, "password": "short"}).status_code == 422
    assert admin_client.post("/users", json={**NEW_USER, "username": "Bob S"}).status_code == 422


def test_admin_changes_a_users_role(admin_client):
    created = admin_client.post("/users", json=NEW_USER).json()
    response = admin_client.patch(f"/users/{created['id']}", json={"role": "operator"})
    assert response.status_code == 200
    assert response.json()["role"] == "operator"


def test_the_last_active_admin_cannot_be_removed(admin_client):
    me = admin_client.get("/auth/me").json()
    assert admin_client.patch(f"/users/{me['id']}", json={"role": "viewer"}).status_code == 409
    assert admin_client.patch(f"/users/{me['id']}", json={"is_active": False}).status_code == 409


def test_an_admin_can_step_down_once_another_admin_exists(admin_client):
    admin_client.post("/users", json={**NEW_USER, "role": "admin"})
    me = admin_client.get("/auth/me").json()

    assert admin_client.patch(f"/users/{me['id']}", json={"role": "viewer"}).status_code == 200
    # The same token loses admin rights on its very next request.
    assert admin_client.get("/users").status_code == 403


def test_unknown_user_is_404(admin_client):
    assert admin_client.patch("/users/nope", json={"role": "admin"}).status_code == 404
