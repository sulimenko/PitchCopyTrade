from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.main import create_app


def _build_client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.preview.get_settings",
        lambda: SimpleNamespace(app=SimpleNamespace(preview_enabled=True)),
    )
    return TestClient(create_app())


def test_preview_root_renders_landing(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        response = client.get("/preview")

        assert response.status_code == 200
        assert "Preview surfaces without auth friction" in response.text
        assert "/preview/app/catalog" in response.text
        assert "/preview/admin/dashboard" in response.text


def test_preview_miniapp_catalog_is_self_contained(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        response = client.get("/preview/app/catalog")

        assert response.status_code == 200
        assert "Preview Subscriber" in response.text
        assert "Straddle Pro" in response.text
        assert "/preview/app/status" in response.text
        assert 'href="/app/status"' not in response.text


def test_preview_staff_dashboards_render(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        admin_response = client.get("/preview/admin/dashboard")
        author_response = client.get("/preview/author/dashboard")

        assert admin_response.status_code == 200
        assert "Preview Admin" in admin_response.text
        assert "Operational center" in admin_response.text

        assert author_response.status_code == 200
        assert "Preview Author Desk" in author_response.text
        assert "Preview Author" in author_response.text
