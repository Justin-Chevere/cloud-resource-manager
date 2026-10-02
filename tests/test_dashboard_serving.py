from fastapi.testclient import TestClient

from app.main import create_app


def _build(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>dashboard build</title>")
    return tmp_path


def test_serves_the_built_dashboard_at_the_root(tmp_path):
    client = TestClient(create_app(dashboard_dir=_build(tmp_path)))

    response = client.get("/")

    assert response.status_code == 200
    assert "dashboard build" in response.text


def test_api_routes_still_win_over_the_dashboard(tmp_path):
    client = TestClient(create_app(dashboard_dir=_build(tmp_path)))

    assert client.get("/openapi.json").json()["info"]["title"] == "cloud-resource-manager"
    assert client.get("/resources").status_code == 401


def test_without_a_build_there_is_no_dashboard(tmp_path):
    client = TestClient(create_app(dashboard_dir=tmp_path / "missing"))

    assert client.get("/").status_code == 404
