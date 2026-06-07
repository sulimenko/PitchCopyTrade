from fastapi import Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
import pytest

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
        assert payload["storage"] == "localfs"
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


async def _async_noop(*_args, **_kwargs) -> None:
    return None


def test_proxy_headers_middleware_keeps_static_urls_https(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pitchcopytrade.api.lifespan._run_seeders", _async_noop)
    monkeypatch.setattr("pitchcopytrade.api.lifespan._init_arq_pool", _async_noop)

    app = create_app()

    @app.get("/_test/static-url")
    async def static_url(request: Request) -> PlainTextResponse:
        return PlainTextResponse(str(request.url_for("static", path="staff/ag-grid-bootstrap.js")))

    with TestClient(app) as client:
        response = client.get(
            "/_test/static-url",
            headers={
                "X-Forwarded-Proto": "https",
                "X-Forwarded-For": "10.0.0.7",
            },
        )

        assert response.status_code == 200
        assert response.text == "https://testserver/static/staff/ag-grid-bootstrap.js"
