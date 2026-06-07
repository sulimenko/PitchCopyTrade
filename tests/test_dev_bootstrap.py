from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from pitchcopytrade.api.deps.repositories import get_optional_db_session
from pitchcopytrade.api.main import create_app
from pitchcopytrade.core.config import reset_settings_cache


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _configure_local_env(monkeypatch, storage_root: Path) -> None:
    monkeypatch.setenv("APP_NAME", "PitchCopyTrade")
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("APP_HOST", "127.0.0.1")
    monkeypatch.setenv("APP_PORT", "8000")
    monkeypatch.setenv("APP_SECRET_KEY", "local-dev-secret")
    monkeypatch.setenv("BASE_URL", "http://127.0.0.1:8000")
    monkeypatch.setenv("ADMIN_BASE_URL", "http://127.0.0.1:8000/admin")
    monkeypatch.setenv("APP_DATA_MODE", "file")
    monkeypatch.setenv("APP_PREVIEW_ENABLED", "true")
    monkeypatch.setenv("APP_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "local-token")
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", "local_preview_bot")
    monkeypatch.setenv("TELEGRAM_USE_WEBHOOK", "false")
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", "unused")
    monkeypatch.setenv("DATABASE_URL", "")
    monkeypatch.setenv("INTERNAL_API_SECRET", "local-internal-secret")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("SBP_PROVIDER", "stub_manual")
    monkeypatch.setenv("SBP_STUB_CONFIRMATION_MODE", "manual")
    monkeypatch.setenv("TINKOFF_TERMINAL_KEY", "__FILL_ME__")
    monkeypatch.setenv("TINKOFF_SECRET_KEY", "__FILL_ME__")
    monkeypatch.setenv("TRIAL_ENABLED", "true")
    monkeypatch.setenv("PROMO_ENABLED", "true")
    monkeypatch.setenv("AUTORENEW_ENABLED", "true")
    monkeypatch.setenv("BASE_TIMEZONE", "Europe/Moscow")
    monkeypatch.setenv("AUTH_SESSION_TTL_SECONDS", "86400")
    monkeypatch.setenv("AUTH_SESSION_COOKIE_NAME", "pitchcopytrade_session")
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("LOG_JSON", "false")
    reset_settings_cache()


def test_dev_bootstrap_grants_staff_and_app_access(monkeypatch, tmp_path: Path) -> None:
    storage_root = tmp_path / "storage"
    storage_root.mkdir(parents=True)
    shutil.copytree(PROJECT_ROOT / "storage" / "seed", storage_root / "seed", dirs_exist_ok=True)

    _configure_local_env(monkeypatch, storage_root)

    app = create_app()

    async def override_optional_db_session():
        yield None

    app.dependency_overrides[get_optional_db_session] = override_optional_db_session

    with TestClient(app) as client:
        page = client.get("/dev/bootstrap")

        assert page.status_code == 200
        assert "local-dev-password" in page.text

        response = client.post("/dev/bootstrap", data={"mode": "author"}, follow_redirects=False)

        assert response.status_code == 303
        assert response.headers["location"] == "/author/dashboard"
        assert "pitchcopytrade_session=" in response.headers["set-cookie"]
        assert "pitchcopytrade_session_staff_mode=author" in response.headers["set-cookie"]
        assert "pitchcopytrade_session_tg=" in response.headers["set-cookie"]

        staff_page = client.get("/author/dashboard")
        catalog_page = client.get("/app/catalog")
        moderation_page = client.get("/moderation/queue")

        assert staff_page.status_code == 200
        assert catalog_page.status_code == 200
        assert moderation_page.status_code == 200
