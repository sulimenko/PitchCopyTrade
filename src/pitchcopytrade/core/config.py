from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class EnvName:
    APP_NAME = "APP_NAME"
    APP_ENV = "APP_ENV"
    APP_HOST = "APP_HOST"
    APP_PORT = "APP_PORT"
    APP_SECRET_KEY = "APP_SECRET_KEY"
    BASE_URL = "BASE_URL"
    ADMIN_BASE_URL = "ADMIN_BASE_URL"
    TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
    TELEGRAM_BOT_USERNAME = "TELEGRAM_BOT_USERNAME"
    TELEGRAM_USE_WEBHOOK = "TELEGRAM_USE_WEBHOOK"
    TELEGRAM_WEBHOOK_SECRET = "TELEGRAM_WEBHOOK_SECRET"
    DATABASE_URL = "DATABASE_URL"
    ALEMBIC_DATABASE_URL = "ALEMBIC_DATABASE_URL"
    POSTGRES_DB = "POSTGRES_DB"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
    MINIO_ENDPOINT = "MINIO_ENDPOINT"
    MINIO_PUBLIC_URL = "MINIO_PUBLIC_URL"
    MINIO_ROOT_USER = "MINIO_ROOT_USER"
    MINIO_ROOT_PASSWORD = "MINIO_ROOT_PASSWORD"
    MINIO_BUCKET_UPLOADS = "MINIO_BUCKET_UPLOADS"
    MINIO_SECURE = "MINIO_SECURE"
    SBP_PROVIDER = "SBP_PROVIDER"
    SBP_STUB_CONFIRMATION_MODE = "SBP_STUB_CONFIRMATION_MODE"
    TINKOFF_TERMINAL_KEY = "TINKOFF_TERMINAL_KEY"
    TINKOFF_SECRET_KEY = "TINKOFF_SECRET_KEY"
    TRIAL_ENABLED = "TRIAL_ENABLED"
    PROMO_ENABLED = "PROMO_ENABLED"
    AUTORENEW_ENABLED = "AUTORENEW_ENABLED"
    BASE_TIMEZONE = "BASE_TIMEZONE"
    LOG_LEVEL = "LOG_LEVEL"
    LOG_JSON = "LOG_JSON"


def _normalize_secret(value: SecretStr | str) -> str:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return value


def _is_placeholder(value: SecretStr | str) -> bool:
    normalized = _normalize_secret(value).strip()
    return not normalized or normalized.startswith("__FILL_ME__")


class AppSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    env: str
    host: str
    port: int
    secret_key: SecretStr
    base_url: str
    admin_base_url: str
    base_timezone: str


class TelegramSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    bot_token: SecretStr
    bot_username: str
    use_webhook: bool
    webhook_secret: SecretStr


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    alembic_url: str
    db_name: str
    user: str
    password: SecretStr


class MinioSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    endpoint: str
    public_url: str
    root_user: str
    root_password: SecretStr
    bucket_uploads: str
    secure: bool


class PaymentSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: str
    stub_confirmation_mode: str
    tinkoff_terminal_key: SecretStr
    tinkoff_secret_key: SecretStr


class FeatureSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    trial_enabled: bool
    promo_enabled: bool
    autorenew_enabled: bool


class LoggingSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: str
    json_logs: bool


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="PitchCopyTrade", alias=EnvName.APP_NAME)
    app_env: str = Field(default="development", alias=EnvName.APP_ENV)
    app_host: str = Field(default="0.0.0.0", alias=EnvName.APP_HOST)
    app_port: int = Field(default=8000, alias=EnvName.APP_PORT)
    app_secret_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.APP_SECRET_KEY)
    base_url: str = Field(default="http://localhost:8000", alias=EnvName.BASE_URL)
    admin_base_url: str = Field(default="http://localhost:8000/admin", alias=EnvName.ADMIN_BASE_URL)

    telegram_bot_token: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TELEGRAM_BOT_TOKEN)
    telegram_bot_username: str = Field(default="__FILL_ME__", alias=EnvName.TELEGRAM_BOT_USERNAME)
    telegram_use_webhook: bool = Field(default=False, alias=EnvName.TELEGRAM_USE_WEBHOOK)
    telegram_webhook_secret: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TELEGRAM_WEBHOOK_SECRET)

    database_url: str = Field(alias=EnvName.DATABASE_URL)
    alembic_database_url: str = Field(alias=EnvName.ALEMBIC_DATABASE_URL)
    postgres_db: str = Field(default="pitchcopytrade", alias=EnvName.POSTGRES_DB)
    postgres_user: str = Field(default="pitchcopytrade", alias=EnvName.POSTGRES_USER)
    postgres_password: SecretStr = Field(default=SecretStr("pitchcopytrade"), alias=EnvName.POSTGRES_PASSWORD)

    minio_endpoint: str = Field(alias=EnvName.MINIO_ENDPOINT)
    minio_public_url: str = Field(alias=EnvName.MINIO_PUBLIC_URL)
    minio_root_user: str = Field(alias=EnvName.MINIO_ROOT_USER)
    minio_root_password: SecretStr = Field(alias=EnvName.MINIO_ROOT_PASSWORD)
    minio_bucket_uploads: str = Field(alias=EnvName.MINIO_BUCKET_UPLOADS)
    minio_secure: bool = Field(default=False, alias=EnvName.MINIO_SECURE)

    sbp_provider: str = Field(default="stub_manual", alias=EnvName.SBP_PROVIDER)
    sbp_stub_confirmation_mode: str = Field(default="manual", alias=EnvName.SBP_STUB_CONFIRMATION_MODE)
    tinkoff_terminal_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TINKOFF_TERMINAL_KEY)
    tinkoff_secret_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TINKOFF_SECRET_KEY)

    trial_enabled: bool = Field(default=True, alias=EnvName.TRIAL_ENABLED)
    promo_enabled: bool = Field(default=True, alias=EnvName.PROMO_ENABLED)
    autorenew_enabled: bool = Field(default=True, alias=EnvName.AUTORENEW_ENABLED)
    base_timezone: str = Field(default="Europe/Moscow", alias=EnvName.BASE_TIMEZONE)

    log_level: str = Field(default="INFO", alias=EnvName.LOG_LEVEL)
    log_json: bool = Field(default=False, alias=EnvName.LOG_JSON)

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}")
        return normalized

    @field_validator("base_url", "admin_base_url", "minio_public_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value.rstrip("/")

    @field_validator("database_url", "alembic_database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError("Database URL must use postgresql+asyncpg://")
        return value

    @field_validator("minio_bucket_uploads")
    @classmethod
    def validate_bucket_name(cls, value: str) -> str:
        normalized = value.strip().lower()
        if len(normalized) < 3:
            raise ValueError("MINIO_BUCKET_UPLOADS must be at least 3 chars")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return normalized

    @field_validator("telegram_webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        if info.data.get("telegram_use_webhook") and _is_placeholder(value):
            raise ValueError("TELEGRAM_WEBHOOK_SECRET is required when TELEGRAM_USE_WEBHOOK=true")
        return value

    @property
    def app(self) -> AppSettings:
        return AppSettings(
            name=self.app_name,
            env=self.app_env,
            host=self.app_host,
            port=self.app_port,
            secret_key=self.app_secret_key,
            base_url=self.base_url,
            admin_base_url=self.admin_base_url,
            base_timezone=self.base_timezone,
        )

    @property
    def telegram(self) -> TelegramSettings:
        return TelegramSettings(
            bot_token=self.telegram_bot_token,
            bot_username=self.telegram_bot_username,
            use_webhook=self.telegram_use_webhook,
            webhook_secret=self.telegram_webhook_secret,
        )

    @property
    def database(self) -> DatabaseSettings:
        return DatabaseSettings(
            url=self.database_url,
            alembic_url=self.alembic_database_url,
            db_name=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
        )

    @property
    def minio(self) -> MinioSettings:
        return MinioSettings(
            endpoint=self.minio_endpoint,
            public_url=self.minio_public_url,
            root_user=self.minio_root_user,
            root_password=self.minio_root_password,
            bucket_uploads=self.minio_bucket_uploads,
            secure=self.minio_secure,
        )

    @property
    def payments(self) -> PaymentSettings:
        return PaymentSettings(
            provider=self.sbp_provider,
            stub_confirmation_mode=self.sbp_stub_confirmation_mode,
            tinkoff_terminal_key=self.tinkoff_terminal_key,
            tinkoff_secret_key=self.tinkoff_secret_key,
        )

    @property
    def features(self) -> FeatureSettings:
        return FeatureSettings(
            trial_enabled=self.trial_enabled,
            promo_enabled=self.promo_enabled,
            autorenew_enabled=self.autorenew_enabled,
        )

    @property
    def logging(self) -> LoggingSettings:
        return LoggingSettings(level=self.log_level, json_logs=self.log_json)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
