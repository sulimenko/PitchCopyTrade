from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl


class TelegramWebAppAuthError(ValueError):
    pass


@dataclass(slots=True)
class TelegramWebAppProfile:
    telegram_user_id: int
    username: str | None
    first_name: str | None
    last_name: str | None
    language_code: str | None


def validate_telegram_webapp_init_data(
    init_data: str,
    *,
    bot_token: str,
    max_age_seconds: int = 3600,
    now: datetime | None = None,
) -> dict[str, str]:
    if not init_data.strip():
        raise TelegramWebAppAuthError("Empty init data")

    items = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = items.pop("hash", None)
    items.pop("signature", None)
    if not received_hash:
        raise TelegramWebAppAuthError("Missing hash")

    data_check_string = "\n".join(f"{key}={value}" for key, value in sorted(items.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramWebAppAuthError("Invalid hash")

    auth_date = int(items.get("auth_date", "0"))
    if auth_date <= 0:
        raise TelegramWebAppAuthError("Invalid auth date")
    reference_now = now or datetime.now(timezone.utc)
    if int(reference_now.timestamp()) - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("Expired init data")

    return items


def extract_telegram_webapp_profile(data: dict[str, str]) -> TelegramWebAppProfile:
    raw_user = data.get("user")
    if not raw_user:
        raise TelegramWebAppAuthError("Missing user payload")
    try:
        user_payload = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError("Invalid user payload") from exc

    telegram_user_id = int(user_payload["id"])
    return TelegramWebAppProfile(
        telegram_user_id=telegram_user_id,
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
        language_code=user_payload.get("language_code"),
    )
