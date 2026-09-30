def _create(client, name="web-1", image="nginx:latest", **extra):
    return client.post("/resources", json={"name": name, "image": image, **extra})


def test_create_starts_pending_with_desired_running(client):
    response = _create(client)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "web-1"
    assert body["desired_state"] == "running"
    # Nothing has reconciled it yet, so reality hasn't caught up.
    assert body["actual_state"] == "pending"


def test_duplicate_name_is_conflict(client):
    _create(client)
    assert _create(client).status_code == 409


def test_invalid_name_is_rejected(client):
    assert _create(client, name="Bad Name!").status_code == 422


def test_cannot_create_as_deleted(client):
    assert _create(client, desired_state="deleted").status_code == 422


def test_list_and_get(client):
    created = _create(client).json()
    _create(client, name="web-2")

    listed = client.get("/resources").json()
    assert [r["name"] for r in listed] == ["web-1", "web-2"]

    fetched = client.get(f"/resources/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_unknown_is_404(client):
    assert client.get("/resources/nope").status_code == 404


def test_patch_changes_desired_state_only(client):
    created = _create(client).json()
    response = client.patch(f"/resources/{created['id']}", json={"desired_state": "stopped"})
    assert response.status_code == 200
    assert response.json()["desired_state"] == "stopped"
    assert response.json()["actual_state"] == "pending"


def test_delete_is_accepted_and_marks_desired_deleted(client):
    created = _create(client).json()
    response = client.delete(f"/resources/{created['id']}")
    assert response.status_code == 202
    assert response.json()["desired_state"] == "deleted"


def test_cannot_patch_a_resource_being_deleted(client):
    created = _create(client).json()
    client.delete(f"/resources/{created['id']}")
    response = client.patch(f"/resources/{created['id']}", json={"desired_state": "running"})
    assert response.status_code == 409
