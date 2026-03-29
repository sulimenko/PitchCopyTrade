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
    APP_DATA_MODE = "APP_DATA_MODE"
    TELEGRAM_BOT_TOKEN = "TELEGRAM_BOT_TOKEN"
    TELEGRAM_BOT_USERNAME = "TELEGRAM_BOT_USERNAME"
    TELEGRAM_USE_WEBHOOK = "TELEGRAM_USE_WEBHOOK"
    TELEGRAM_WEBHOOK_SECRET = "TELEGRAM_WEBHOOK_SECRET"
    DATABASE_URL = "DATABASE_URL"
    POSTGRES_DB = "POSTGRES_DB"
    POSTGRES_USER = "POSTGRES_USER"
    POSTGRES_PASSWORD = "POSTGRES_PASSWORD"
    SBP_PROVIDER = "SBP_PROVIDER"
    SBP_STUB_CONFIRMATION_MODE = "SBP_STUB_CONFIRMATION_MODE"
    TINKOFF_TERMINAL_KEY = "TINKOFF_TERMINAL_KEY"
    TINKOFF_SECRET_KEY = "TINKOFF_SECRET_KEY"
    TRIAL_ENABLED = "TRIAL_ENABLED"
    PROMO_ENABLED = "PROMO_ENABLED"
    AUTORENEW_ENABLED = "AUTORENEW_ENABLED"
    BASE_TIMEZONE = "BASE_TIMEZONE"
    AUTH_SESSION_TTL_SECONDS = "AUTH_SESSION_TTL_SECONDS"
    AUTH_SESSION_COOKIE_NAME = "AUTH_SESSION_COOKIE_NAME"
    APP_STORAGE_ROOT = "APP_STORAGE_ROOT"
    APP_PREVIEW_ENABLED = "APP_PREVIEW_ENABLED"
    LOG_LEVEL = "LOG_LEVEL"
    LOG_JSON = "LOG_JSON"
    LOG_FILE = "LOG_FILE"
    INTERNAL_API_SECRET = "INTERNAL_API_SECRET"
    REDIS_URL = "REDIS_URL"
    INSTRUMENT_QUOTE_PROVIDER_ENABLED = "INSTRUMENT_QUOTE_PROVIDER_ENABLED"
    INSTRUMENT_QUOTE_PROVIDER_BASE_URL = "INSTRUMENT_QUOTE_PROVIDER_BASE_URL"
    INSTRUMENT_QUOTE_TIMEOUT_SECONDS = "INSTRUMENT_QUOTE_TIMEOUT_SECONDS"
    INSTRUMENT_QUOTE_CACHE_TTL_SECONDS = "INSTRUMENT_QUOTE_CACHE_TTL_SECONDS"
    TELEGRAM_WEBHOOK_URL = "TELEGRAM_WEBHOOK_URL"
    SMTP_HOST = "SMTP_HOST"
    SMTP_PORT = "SMTP_PORT"
    SMTP_SSL = "SMTP_SSL"
    SMTP_USER = "SMTP_USER"
    SMTP_PASSWORD = "SMTP_PASSWORD"
    SMTP_FROM = "SMTP_FROM"
    SMTP_FROM_NAME = "SMTP_FROM_NAME"
    ADMIN_TELEGRAM_ID = "ADMIN_TELEGRAM_ID"
    ADMIN_EMAIL = "ADMIN_EMAIL"
    GOOGLE_CLIENT_ID = "GOOGLE_CLIENT_ID"
    GOOGLE_CLIENT_SECRET = "GOOGLE_CLIENT_SECRET"
    YANDEX_CLIENT_ID = "YANDEX_CLIENT_ID"
    YANDEX_CLIENT_SECRET = "YANDEX_CLIENT_SECRET"


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
    data_mode: str
    preview_enabled: bool


class TelegramSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    bot_token: SecretStr
    bot_username: str
    use_webhook: bool
    webhook_secret: SecretStr


class DatabaseSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    url: str
    db_name: str
    user: str
    password: SecretStr


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
    file_path: str | None = None


class AuthSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    session_ttl_seconds: int
    session_cookie_name: str


class NotificationSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    internal_api_secret: SecretStr
    redis_url: str
    smtp_host: str
    smtp_port: int
    smtp_ssl: bool
    smtp_user: str
    smtp_password: SecretStr
    smtp_from: str
    smtp_from_name: str


class InstrumentQuoteSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider_enabled: bool
    provider_base_url: str
    timeout_seconds: float
    cache_ttl_seconds: int


class StorageSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    root: str
    seed_root: str
    runtime_root: str
    blob_root: str
    json_root: str
    seed_blob_root: str
    seed_json_root: str


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="PitchCopyTrade", alias=EnvName.APP_NAME)
    app_env: str = Field(default="development", alias=EnvName.APP_ENV)
    app_host: str = Field(default="0.0.0.0", alias=EnvName.APP_HOST)
    app_port: int = Field(default=8000, alias=EnvName.APP_PORT)
    app_secret_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.APP_SECRET_KEY)
    base_url: str = Field(default="http://localhost:8000", alias=EnvName.BASE_URL)
    admin_base_url: str = Field(default="http://localhost:8000/admin", alias=EnvName.ADMIN_BASE_URL)
    app_data_mode: str = Field(default="db", alias=EnvName.APP_DATA_MODE)

    telegram_bot_token: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TELEGRAM_BOT_TOKEN)
    telegram_bot_username: str = Field(default="__FILL_ME__", alias=EnvName.TELEGRAM_BOT_USERNAME)
    telegram_use_webhook: bool = Field(default=False, alias=EnvName.TELEGRAM_USE_WEBHOOK)
    telegram_webhook_secret: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TELEGRAM_WEBHOOK_SECRET)

    database_url: str = Field(default="", alias=EnvName.DATABASE_URL)
    postgres_db: str = Field(default="pitchcopytrade", alias=EnvName.POSTGRES_DB)
    postgres_user: str = Field(default="pitchcopytrade", alias=EnvName.POSTGRES_USER)
    postgres_password: SecretStr = Field(default=SecretStr("pitchcopytrade"), alias=EnvName.POSTGRES_PASSWORD)

    sbp_provider: str = Field(default="stub_manual", alias=EnvName.SBP_PROVIDER)
    sbp_stub_confirmation_mode: str = Field(default="manual", alias=EnvName.SBP_STUB_CONFIRMATION_MODE)
    tinkoff_terminal_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TINKOFF_TERMINAL_KEY)
    tinkoff_secret_key: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.TINKOFF_SECRET_KEY)

    trial_enabled: bool = Field(default=True, alias=EnvName.TRIAL_ENABLED)
    promo_enabled: bool = Field(default=True, alias=EnvName.PROMO_ENABLED)
    autorenew_enabled: bool = Field(default=True, alias=EnvName.AUTORENEW_ENABLED)
    base_timezone: str = Field(default="Europe/Moscow", alias=EnvName.BASE_TIMEZONE)
    auth_session_ttl_seconds: int = Field(default=60 * 60 * 24, alias=EnvName.AUTH_SESSION_TTL_SECONDS)
    auth_session_cookie_name: str = Field(default="pitchcopytrade_session", alias=EnvName.AUTH_SESSION_COOKIE_NAME)
    app_storage_root: str = Field(default="storage", alias=EnvName.APP_STORAGE_ROOT)
    app_preview_enabled: bool = Field(default=False, alias=EnvName.APP_PREVIEW_ENABLED)

    log_level: str = Field(default="INFO", alias=EnvName.LOG_LEVEL)
    log_json: bool = Field(default=False, alias=EnvName.LOG_JSON)
    log_file: str | None = Field(default=None, alias=EnvName.LOG_FILE)

    internal_api_secret: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.INTERNAL_API_SECRET)
    redis_url: str = Field(default="redis://localhost:6379/0", alias=EnvName.REDIS_URL)
    instrument_quote_provider_enabled: bool = Field(default=False, alias=EnvName.INSTRUMENT_QUOTE_PROVIDER_ENABLED)
    instrument_quote_provider_base_url: str = Field(
        default="https://meta.pbull.kz/api/marketData/forceDataSymbol",
        alias=EnvName.INSTRUMENT_QUOTE_PROVIDER_BASE_URL,
    )
    instrument_quote_timeout_seconds: float = Field(default=10.0, alias=EnvName.INSTRUMENT_QUOTE_TIMEOUT_SECONDS)
    instrument_quote_cache_ttl_seconds: int = Field(default=30, alias=EnvName.INSTRUMENT_QUOTE_CACHE_TTL_SECONDS)
    telegram_webhook_url: str = Field(default="", alias=EnvName.TELEGRAM_WEBHOOK_URL)
    smtp_host: str = Field(default="relay.ptfin.kz", alias=EnvName.SMTP_HOST)
    smtp_port: int = Field(default=465, alias=EnvName.SMTP_PORT)
    smtp_ssl: bool = Field(default=True, alias=EnvName.SMTP_SSL)
    smtp_user: str = Field(default="pct@ptfin.ru", alias=EnvName.SMTP_USER)
    smtp_password: SecretStr = Field(default=SecretStr("__FILL_ME__"), alias=EnvName.SMTP_PASSWORD)
    smtp_from: str = Field(default="pct@ptfin.ru", alias=EnvName.SMTP_FROM)
    smtp_from_name: str = Field(default="PitchCopyTrade", alias=EnvName.SMTP_FROM_NAME)
    admin_telegram_id: int | None = Field(default=None, alias=EnvName.ADMIN_TELEGRAM_ID)
    admin_email: str | None = Field(default=None, alias=EnvName.ADMIN_EMAIL)

    # X4.2: OAuth configuration (optional, disabled if not set)
    google_client_id: str | None = Field(default=None, alias=EnvName.GOOGLE_CLIENT_ID)
    google_client_secret: SecretStr | None = Field(default=None, alias=EnvName.GOOGLE_CLIENT_SECRET)
    yandex_client_id: str | None = Field(default=None, alias=EnvName.YANDEX_CLIENT_ID)
    yandex_client_secret: SecretStr | None = Field(default=None, alias=EnvName.YANDEX_CLIENT_SECRET)

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"APP_ENV must be one of {sorted(allowed)}")
        return normalized

    @field_validator("app_data_mode")
    @classmethod
    def validate_data_mode(cls, value: str) -> str:
        allowed = {"db", "file"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError(f"APP_DATA_MODE must be one of {sorted(allowed)}")
        return normalized

    @field_validator("base_url", "admin_base_url")
    @classmethod
    def validate_http_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value.rstrip("/")

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if info.data.get("app_data_mode") == "file" and not normalized:
            return normalized
        if not normalized.startswith("postgresql+asyncpg://"):
            raise ValueError("Database URL must use postgresql+asyncpg://")
        return normalized

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        allowed = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}
        normalized = value.strip().upper()
        if normalized not in allowed:
            raise ValueError(f"LOG_LEVEL must be one of {sorted(allowed)}")
        return normalized

    @field_validator("log_file")
    @classmethod
    def validate_log_file(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("auth_session_ttl_seconds")
    @classmethod
    def validate_session_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("AUTH_SESSION_TTL_SECONDS must be positive")
        return value

    @field_validator("instrument_quote_timeout_seconds")
    @classmethod
    def validate_quote_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("INSTRUMENT_QUOTE_TIMEOUT_SECONDS must be positive")
        return value

    @field_validator("instrument_quote_cache_ttl_seconds")
    @classmethod
    def validate_quote_cache_ttl(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("INSTRUMENT_QUOTE_CACHE_TTL_SECONDS must be positive")
        return value

    @field_validator("app_storage_root")
    @classmethod
    def validate_storage_root(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("APP_STORAGE_ROOT must not be empty")
        return normalized

    @field_validator("app_preview_enabled")
    @classmethod
    def validate_preview_enabled(cls, value: bool) -> bool:
        return bool(value)

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
            data_mode=self.app_data_mode,
            preview_enabled=self.app_preview_enabled,
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
            db_name=self.postgres_db,
            user=self.postgres_user,
            password=self.postgres_password,
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
        return LoggingSettings(level=self.log_level, json_logs=self.log_json, file_path=self.log_file)

    @property
    def auth(self) -> AuthSettings:
        return AuthSettings(
            session_ttl_seconds=self.auth_session_ttl_seconds,
            session_cookie_name=self.auth_session_cookie_name,
        )

    @property
    def notifications(self) -> NotificationSettings:
        return NotificationSettings(
            internal_api_secret=self.internal_api_secret,
            redis_url=self.redis_url,
            smtp_host=self.smtp_host,
            smtp_port=self.smtp_port,
            smtp_ssl=self.smtp_ssl,
            smtp_user=self.smtp_user,
            smtp_password=self.smtp_password,
            smtp_from=self.smtp_from,
            smtp_from_name=self.smtp_from_name,
        )

    @property
    def instrument_quotes(self) -> InstrumentQuoteSettings:
        return InstrumentQuoteSettings(
            provider_enabled=self.instrument_quote_provider_enabled,
            provider_base_url=self.instrument_quote_provider_base_url.rstrip("/"),
            timeout_seconds=self.instrument_quote_timeout_seconds,
            cache_ttl_seconds=self.instrument_quote_cache_ttl_seconds,
        )

    @property
    def storage(self) -> StorageSettings:
        root = self.app_storage_root
        seed_root = f"{root}/seed"
        runtime_root = f"{root}/runtime"
        return StorageSettings(
            root=root,
            seed_root=seed_root,
            runtime_root=runtime_root,
            blob_root=f"{runtime_root}/blob",
            json_root=f"{runtime_root}/json",
            seed_blob_root=f"{seed_root}/blob",
            seed_json_root=f"{seed_root}/json",
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
