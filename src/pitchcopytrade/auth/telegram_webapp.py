from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl


logger = logging.getLogger(__name__)


class TelegramWebAppAuthError(ValueError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail


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
        raise TelegramWebAppAuthError("empty_init_data", "Empty init data")

    items = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = items.pop("hash", None)
    had_signature = "signature" in items
    signature_value = items.pop("signature", None)
    if not received_hash:
        raise TelegramWebAppAuthError("missing_hash", "Missing hash")

    data_check_items_without_signature = dict(items)
    data_check_string_without_signature = "\n".join(
        f"{key}={value}" for key, value in sorted(data_check_items_without_signature.items())
    )
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash_without_signature = hmac.new(
        secret_key,
        data_check_string_without_signature.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    expected_hash_with_signature = None
    data_check_string_with_signature = None
    if had_signature and signature_value is not None:
        items_with_signature = dict(items)
        items_with_signature["signature"] = signature_value
        data_check_string_with_signature = "\n".join(
            f"{key}={value}" for key, value in sorted(items_with_signature.items())
        )
        expected_hash_with_signature = hmac.new(
            secret_key,
            data_check_string_with_signature.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    match_without_signature = hmac.compare_digest(expected_hash_without_signature, received_hash)
    match_with_signature = (
        hmac.compare_digest(expected_hash_with_signature, received_hash)
        if expected_hash_with_signature is not None
        else False
    )

    logger.info(
        "initData validation keys=%s had_signature=%s received_hash_prefix=%s hash_without_signature_prefix=%s match_without_signature=%s hash_with_signature_prefix=%s match_with_signature=%s data_check_len_without_signature=%s data_check_len_with_signature=%s bot_token_fingerprint=%s",
        sorted(items.keys()),
        had_signature,
        received_hash[:12] if received_hash else "-",
        expected_hash_without_signature[:12],
        match_without_signature,
        expected_hash_with_signature[:12] if expected_hash_with_signature else "-",
        match_with_signature,
        len(data_check_string_without_signature),
        len(data_check_string_with_signature) if data_check_string_with_signature is not None else "-",
        hashlib.sha256(bot_token.encode("utf-8")).hexdigest()[:12],
    )

    if match_without_signature:
        pass
    elif match_with_signature:
        items["signature"] = signature_value
        logger.warning("initData validated WITH signature in data_check_string")
    else:
        raise TelegramWebAppAuthError("invalid_hash", "Invalid hash")

    try:
        auth_date = int(items.get("auth_date", "0"))
    except (TypeError, ValueError):
        raise TelegramWebAppAuthError("invalid_auth_date", "Invalid auth date")
    if auth_date <= 0:
        raise TelegramWebAppAuthError("invalid_auth_date", "Invalid auth date")
    reference_now = now or datetime.now(timezone.utc)
    if int(reference_now.timestamp()) - auth_date > max_age_seconds:
        raise TelegramWebAppAuthError("expired_init_data", "Expired init data")

    return items


def describe_telegram_webapp_init_data(
    init_data: str,
    *,
    now: datetime | None = None,
) -> dict[str, int | bool | None]:
    items = dict(parse_qsl(init_data, keep_blank_values=True))
    auth_date_age_seconds: int | None = None
    raw_auth_date = items.get("auth_date")
    try:
        auth_date = int(raw_auth_date) if raw_auth_date is not None else None
    except (TypeError, ValueError):
        auth_date = None
    if auth_date is not None and auth_date > 0:
        reference_now = now or datetime.now(timezone.utc)
        auth_date_age_seconds = int(reference_now.timestamp()) - auth_date
    return {
        "length": len(init_data),
        "has_hash": "hash" in items,
        "has_auth_date": "auth_date" in items,
        "has_user": "user" in items,
        "has_signature": "signature" in items,
        "auth_date_age_seconds": auth_date_age_seconds,
    }


def extract_telegram_webapp_profile(data: dict[str, str]) -> TelegramWebAppProfile:
    raw_user = data.get("user")
    if not raw_user:
        raise TelegramWebAppAuthError("missing_user_payload", "Missing user payload")
    try:
        user_payload = json.loads(raw_user)
    except json.JSONDecodeError as exc:
        raise TelegramWebAppAuthError("invalid_user_payload", "Invalid user payload") from exc

    try:
        telegram_user_id = int(user_payload["id"])
    except (KeyError, TypeError, ValueError) as exc:
        raise TelegramWebAppAuthError("invalid_user_payload", "Invalid user payload") from exc
    return TelegramWebAppProfile(
        telegram_user_id=telegram_user_id,
        username=user_payload.get("username"),
        first_name=user_payload.get("first_name"),
        last_name=user_payload.get("last_name"),
        language_code=user_payload.get("language_code"),
    )
