from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="PitchCopyTrade", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    app_secret_key: str = Field(default="__FILL_ME__", alias="APP_SECRET_KEY")
    base_url: str = Field(default="http://localhost:8000", alias="BASE_URL")
    admin_base_url: str = Field(default="http://localhost:8000/admin", alias="ADMIN_BASE_URL")

    telegram_bot_token: str = Field(default="__FILL_ME__", alias="TELEGRAM_BOT_TOKEN")
    telegram_bot_username: str = Field(default="__FILL_ME__", alias="TELEGRAM_BOT_USERNAME")
    telegram_use_webhook: bool = Field(default=False, alias="TELEGRAM_USE_WEBHOOK")
    telegram_webhook_secret: str = Field(default="__FILL_ME__", alias="TELEGRAM_WEBHOOK_SECRET")

    database_url: str = Field(alias="DATABASE_URL")
    alembic_database_url: str = Field(alias="ALEMBIC_DATABASE_URL")
    postgres_db: str = Field(default="pitchcopytrade", alias="POSTGRES_DB")
    postgres_user: str = Field(default="pitchcopytrade", alias="POSTGRES_USER")
    postgres_password: str = Field(default="pitchcopytrade", alias="POSTGRES_PASSWORD")

    minio_endpoint: str = Field(alias="MINIO_ENDPOINT")
    minio_public_url: str = Field(alias="MINIO_PUBLIC_URL")
    minio_root_user: str = Field(alias="MINIO_ROOT_USER")
    minio_root_password: str = Field(alias="MINIO_ROOT_PASSWORD")
    minio_bucket_uploads: str = Field(alias="MINIO_BUCKET_UPLOADS")
    minio_secure: bool = Field(default=False, alias="MINIO_SECURE")

    sbp_provider: str = Field(default="stub_manual", alias="SBP_PROVIDER")
    sbp_stub_confirmation_mode: str = Field(default="manual", alias="SBP_STUB_CONFIRMATION_MODE")
    tinkoff_terminal_key: str = Field(default="__FILL_ME__", alias="TINKOFF_TERMINAL_KEY")
    tinkoff_secret_key: str = Field(default="__FILL_ME__", alias="TINKOFF_SECRET_KEY")

    trial_enabled: bool = Field(default=True, alias="TRIAL_ENABLED")
    promo_enabled: bool = Field(default=True, alias="PROMO_ENABLED")
    autorenew_enabled: bool = Field(default=True, alias="AUTORENEW_ENABLED")
    base_timezone: str = Field(default="Europe/Moscow", alias="BASE_TIMEZONE")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
