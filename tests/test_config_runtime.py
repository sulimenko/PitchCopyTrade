from __future__ import annotations

import logging

import pytest
from pydantic import ValidationError

from pitchcopytrade.core.config import LoggingSettings, Settings, reset_settings_cache
from pitchcopytrade.core.logging import configure_logging
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
        "APP_DATA_MODE": "db",
        "TELEGRAM_BOT_TOKEN": "123456:valid-token",
        "TELEGRAM_BOT_USERNAME": "pitchcopytrade_bot",
        "TELEGRAM_USE_WEBHOOK": "false",
        "TELEGRAM_WEBHOOK_SECRET": "__FILL_ME__",
        "POSTGRES_DB": "pitchcopytrade",
        "POSTGRES_USER": "pitchcopytrade",
        "POSTGRES_PASSWORD": "pitchcopytrade",
        "DATABASE_URL": "postgresql+asyncpg://pitchcopytrade:pitchcopytrade@postgres:5432/pitchcopytrade",
        "ALEMBIC_DATABASE_URL": "postgresql+asyncpg://pitchcopytrade:pitchcopytrade@postgres:5432/pitchcopytrade",
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
        "APP_STORAGE_ROOT": "storage",
        "LOG_LEVEL": "INFO",
        "LOG_JSON": "false",
        "LOG_FILE": "",
    }


def _make_settings(monkeypatch: pytest.MonkeyPatch, **overrides: str) -> Settings:
    reset_settings_cache()
    monkeypatch.delenv("LOG_FILE", raising=False)
    for key, value in {**_base_env(), **overrides}.items():
        monkeypatch.setenv(key, value)
    return Settings()


def test_settings_expose_typed_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch)

    assert settings.app.name == "PitchCopyTrade"
    assert settings.database.url.startswith("postgresql+asyncpg://")
    assert settings.payments.provider == "stub_manual"
    assert settings.auth.session_ttl_seconds == 86400
    assert settings.auth.session_cookie_name == "pitchcopytrade_session"
    assert settings.app.data_mode == "db"
    assert settings.storage.root == "storage"
    assert settings.storage.seed_root == "storage/seed"
    assert settings.storage.runtime_root == "storage/runtime"
    assert settings.storage.blob_root == "storage/runtime/blob"
    assert settings.storage.json_root == "storage/runtime/json"
    assert settings.storage.seed_blob_root == "storage/seed/blob"
    assert settings.storage.seed_json_root == "storage/seed/json"
    assert settings.logging.level == "INFO"
    assert settings.logging.json_logs is False
    assert settings.logging.file_path is None


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


def test_file_mode_allows_missing_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(
        monkeypatch,
        APP_DATA_MODE="file",
        DATABASE_URL="",
        ALEMBIC_DATABASE_URL="",
    )

    validate_runtime_settings(settings, "api")

    assert settings.app.data_mode == "file"


def test_settings_validate_data_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError, match="APP_DATA_MODE"):
        _make_settings(monkeypatch, APP_DATA_MODE="redis")


def test_settings_expose_log_file_path(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(monkeypatch, LOG_FILE="api.log")

    assert settings.logging.file_path == "api.log"


def test_settings_normalize_quote_provider_origin(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = _make_settings(
        monkeypatch,
        INSTRUMENT_QUOTE_PROVIDER_BASE_URL="http://meta-api-1:8000/api/marketData/forceDataSymbol",
    )

    assert settings.instrument_quote_provider_base_url == "http://meta-api-1:8000"
    assert settings.instrument_quotes.provider_base_url == "http://meta-api-1:8000/api/marketData/forceDataSymbol"


def test_configure_logging_writes_to_file(tmp_path) -> None:
    log_file = tmp_path / "api.log"
    configure_logging(LoggingSettings(level="INFO", json_logs=False, file_path=str(log_file)))

    logging.getLogger("pitchcopytrade.tests").info("hello file logging")

    assert log_file.exists()
    assert "hello file logging" in log_file.read_text(encoding="utf-8")
