def _create(client, name="web-1", image="nginx:latest", **extra):
    return client.post("/resources", json={"name": name, "image": image, **extra})


def test_create_starts_pending_with_desired_running(operator_client):
    response = _create(operator_client)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "web-1"
    assert body["desired_state"] == "running"
    # Nothing has reconciled it yet, so reality hasn't caught up.
    assert body["actual_state"] == "pending"


def test_duplicate_name_is_conflict(operator_client):
    _create(operator_client)
    assert _create(operator_client).status_code == 409


def test_invalid_name_is_rejected(operator_client):
    assert _create(operator_client, name="Bad Name!").status_code == 422


def test_cannot_create_as_deleted(operator_client):
    assert _create(operator_client, desired_state="deleted").status_code == 422


def test_list_and_get(operator_client):
    created = _create(operator_client).json()
    _create(operator_client, name="web-2")

    listed = operator_client.get("/resources").json()
    assert [r["name"] for r in listed] == ["web-1", "web-2"]

    fetched = operator_client.get(f"/resources/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == created["id"]


def test_get_unknown_is_404(operator_client):
    assert operator_client.get("/resources/nope").status_code == 404


def test_patch_changes_desired_state_only(operator_client):
    created = _create(operator_client).json()
    response = operator_client.patch(
        f"/resources/{created['id']}", json={"desired_state": "stopped"}
    )
    assert response.status_code == 200
    assert response.json()["desired_state"] == "stopped"
    assert response.json()["actual_state"] == "pending"


def test_delete_is_accepted_and_marks_desired_deleted(operator_client):
    created = _create(operator_client).json()
    response = operator_client.delete(f"/resources/{created['id']}")
    assert response.status_code == 202
    assert response.json()["desired_state"] == "deleted"


def test_cannot_patch_a_resource_being_deleted(operator_client):
    created = _create(operator_client).json()
    operator_client.delete(f"/resources/{created['id']}")
    response = operator_client.patch(
        f"/resources/{created['id']}", json={"desired_state": "running"}
    )
    assert response.status_code == 409
