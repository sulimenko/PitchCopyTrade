from fastapi.testclient import TestClient

from pitchcopytrade.api.main import create_app


def test_health_endpoint_returns_ok() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_ready_endpoint_reflects_started_app() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"


def test_metadata_route_returns_runtime_metadata() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/metadata")

        assert response.status_code == 200
        payload = response.json()
        assert payload["service"] == "PitchCopyTrade"
        assert payload["data_mode"] in ("db", "file")
        assert payload["storage_root"] == "storage"
        assert payload["storage"] in ("db+minio+localfs", "file+localfs")
        assert payload["payments"] == "stub_manual"
        assert payload["started_at"] is not None


def test_startup_shutdown_hooks_toggle_app_state() -> None:
    app = create_app()

    assert app.state.ready is False

    with TestClient(app):
        assert app.state.ready is True
        assert app.state.started_at is not None

    assert app.state.ready is False
    assert app.state.stopped_at is not None
