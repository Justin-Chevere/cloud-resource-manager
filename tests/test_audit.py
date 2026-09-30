def _create_resource(client, name="web-1"):
    return client.post("/resources", json={"name": name, "image": "nginx"})


def test_resource_changes_are_recorded_with_who_made_them(operator_client, admin_client):
    created = _create_resource(operator_client).json()
    operator_client.patch(f"/resources/{created['id']}", json={"desired_state": "stopped"})
    operator_client.delete(f"/resources/{created['id']}")

    events = admin_client.get("/audit").json()

    assert [e["action"] for e in events] == [
        "resource.delete",
        "resource.update",
        "resource.create",
    ]
    assert {e["actor"] for e in events} == {"operator"}
    assert {e["target_id"] for e in events} == {created["id"]}
    assert events[1]["details"] == {"desired_state": {"from": "running", "to": "stopped"}}


def test_requests_that_change_nothing_are_not_recorded(operator_client, admin_client):
    created = _create_resource(operator_client).json()
    operator_client.patch(f"/resources/{created['id']}", json={"desired_state": "running"})

    assert [e["action"] for e in admin_client.get("/audit").json()] == ["resource.create"]


def test_rejected_requests_are_not_recorded(operator_client, admin_client):
    _create_resource(operator_client)
    assert _create_resource(operator_client).status_code == 409

    assert len(admin_client.get("/audit").json()) == 1


def test_user_management_is_recorded(admin_client):
    new_user = {"username": "bob", "password": "bob-password-123"}
    created = admin_client.post("/users", json=new_user).json()
    admin_client.patch(f"/users/{created['id']}", json={"role": "operator"})

    update, create = admin_client.get("/audit").json()
    assert create["action"] == "user.create"
    assert create["actor"] == "admin"
    assert create["details"] == {"username": "bob", "role": "viewer"}
    assert update["details"] == {"role": {"from": "viewer", "to": "operator"}}


def test_limit_returns_the_most_recent_events(operator_client, admin_client):
    for i in range(3):
        _create_resource(operator_client, name=f"web-{i}")

    events = admin_client.get("/audit", params={"limit": 2}).json()

    assert [e["details"]["name"] for e in events] == ["web-2", "web-1"]
