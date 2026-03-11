from __future__ import annotations

import pytest
from pydantic import ValidationError

from pitchcopytrade.core.config import Settings, reset_settings_cache
from pitchcopytrade.core.runtime import validate_runtime_settings


def _base_env() -> dict[str, str]:
    return {
        "APP_NAME": "PitchCopyTrade",
        "APP_ENV": "test",
        "APP_HOST": "0.0.0.0",
        "APP_PORT": "8000",
        "APP_SECRET_KEY": "test-secret",
        "BASE_URL": "http://localhost:8000",
        "ADMIN_BASE_URL": "http://localhost:8000/admin",
        "TELEGRAM_BOT_TOKEN": "123456:valid-token",
        "TELEGRAM_BOT_USERNAME": "pitchcopytrade_bot",
        "TELEGRAM_USE_WEBHOOK": "false",
        "TELEGRAM_WEBHOOK_SECRET": "__FILL_ME__",
        "POSTGRES_DB": "pitchcopytrade",
        "POSTGRES_USER": "pitchcopytrade",
        "POSTGRES_PASSWORD": "pitchcopytrade",
        "DATABASE_URL": "postgresql+asyncpg://pitchcopytrade:pitchcopytrade@postgres:5432/pitchcopytrade",
        "ALEMBIC_DATABASE_URL": "postgresql+asyncpg://pitchcopytrade:pitchcopytrade@postgres:5432/pitchcopytrade",
        "MINIO_ENDPOINT": "minio:9000",
        "MINIO_PUBLIC_URL": "http://localhost:9000",
        "MINIO_ROOT_USER": "minioadmin",
        "MINIO_ROOT_PASSWORD": "minio-secret",
        "MINIO_BUCKET_UPLOADS": "pitchcopytrade-uploads",
        "MINIO_SECURE": "false",
        "SBP_PROVIDER": "stub_manual",
        "SBP_STUB_CONFIRMATION_MODE": "manual",
        "TINKOFF_TERMINAL_KEY": "__FILL_ME__",
        "TINKOFF_SECRET_KEY": "__FILL_ME__",
        "TRIAL_ENABLED": "true",
        "PROMO_ENABLED": "true",
        "AUTORENEW_ENABLED": "true",
        "BASE_TIMEZONE": "Europe/Moscow",
        "AUTH_SESSION_TTL_SECONDS": "86400",
        "AUTH_SESSION_COOKIE_NAME": "pitchcopytrade_session",
        "LOG_LEVEL": "INFO",
        "LOG_JSON": "false",
    }


def _make_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    reset_settings_cache()
    for key, value in {**_base_env(), **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_settings_expose_typed_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch)

    assert settings.app.name == "PitchCopyTrade"
    assert settings.database.url.startswith("postgresql+asyncpg://")
    assert settings.minio.bucket_uploads == "pitchcopytrade-uploads"
    assert settings.payments.provider == "stub_manual"
    assert settings.auth.session_ttl_seconds == 86400
    assert settings.auth.session_cookie_name == "pitchcopytrade_session"
    assert settings.logging.level == "INFO"
    assert settings.logging.json_logs is False


def test_validate_runtime_settings_fails_on_missing_bot_token(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch, TELEGRAM_BOT_TOKEN="__FILL_ME__")

    with pytest.raises(RuntimeError, match="TELEGRAM_BOT_TOKEN"):
        validate_runtime_settings(settings, "bot")


def test_validate_runtime_settings_requires_tbank_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch, SBP_PROVIDER="tbank")

    with pytest.raises(RuntimeError, match="TINKOFF_SECRET_KEY"):
        validate_runtime_settings(settings, "api")


def test_settings_validate_database_scheme(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="postgresql\\+asyncpg://"):
        _make_settings(monkeypatch, DATABASE_URL="postgresql://localhost/db")
