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
        assert "grid-template-columns:1fr" in response.text


def test_preview_miniapp_catalog_is_self_contained(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        response = client.get("/preview/app/catalog")
        help_response = client.get("/preview/app/help")
        status_response = client.get("/preview/app/status")

        assert response.status_code == 200
        assert "Preview Subscriber" in response.text
        assert "Straddle Pro" in response.text
        assert "/preview/app/subscriptions" in response.text
        assert "/preview/app/timeline" in response.text
        assert 'href="/app/status"' not in response.text
        assert help_response.status_code == 200
        assert "Как пользоваться сервисом" in help_response.text
        assert "grid-template-columns:1fr" in help_response.text
        assert status_response.status_code == 200
        assert "Статус подписки" in status_response.text
        assert "grid-template-columns:1fr" in status_response.text


def test_preview_strategy_detail_has_structured_narrative(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        response = client.get("/preview/app/strategies/straddle-pro")

        assert response.status_code == 200
        assert "Описание" in response.text
        assert "Детально" in response.text
        assert "Тарифы" in response.text
        assert "К стратегии" in response.text


def test_preview_staff_dashboards_render(monkeypatch) -> None:
    with _build_client(monkeypatch) as client:
        admin_response = client.get("/preview/admin/dashboard")
        author_response = client.get("/preview/author/dashboard")

        assert admin_response.status_code == 200
        assert "Preview Admin" in admin_response.text
        assert "Operational center" in admin_response.text
        assert "grid-template-columns:1fr" in admin_response.text

        assert author_response.status_code == 200
        assert "Preview Author Desk" in author_response.text
        assert "Preview Author" in author_response.text
        assert "grid-template-columns:1fr" in author_response.text
