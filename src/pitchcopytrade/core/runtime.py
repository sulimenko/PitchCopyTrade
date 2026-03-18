from __future__ import annotations

from pitchcopytrade.core.config import Settings, _is_placeholder, get_settings
from pitchcopytrade.core.logging import configure_logging


SERVICE_REQUIRED_SECRETS: dict[str, tuple[tuple[str, str | None], ...]] = {
    "api": (
        ("APP_SECRET_KEY", "app_secret_key"),
    ),
    "bot": (
        ("APP_SECRET_KEY", "app_secret_key"),
        ("TELEGRAM_BOT_TOKEN", "telegram_bot_token"),
    ),
    "worker": (
        ("APP_SECRET_KEY", "app_secret_key"),
    ),
}


def validate_runtime_settings(settings: Settings, service_name: str) -> None:
    missing: list[str] = []

    for env_name, attr_name in SERVICE_REQUIRED_SECRETS.get(service_name, ()):
        if _is_placeholder(getattr(settings, attr_name)):
            missing.append(env_name)

    if settings.sbp_provider == "tbank":
        if _is_placeholder(settings.tinkoff_terminal_key):
            missing.append("TINKOFF_TERMINAL_KEY")
        if _is_placeholder(settings.tinkoff_secret_key):
            missing.append("TINKOFF_SECRET_KEY")

    if settings.app_data_mode == "db":
        if not settings.database_url:
            missing.append("DATABASE_URL")
        if _is_placeholder(settings.minio_root_password):
            missing.append("MINIO_ROOT_PASSWORD")

    if missing:
        vars_joined = ", ".join(sorted(set(missing)))
        raise RuntimeError(f"Runtime configuration invalid for {service_name}: fill {vars_joined}")


def bootstrap_runtime(service_name: str) -> Settings:
    settings = get_settings()
    configure_logging(settings.logging)
    validate_runtime_settings(settings, service_name)
    return settings
