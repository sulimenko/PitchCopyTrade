from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone


class TelegramLoginWidgetError(Exception):
    pass


def verify_telegram_login_widget(params: dict, bot_token: str, max_age_seconds: int = 300) -> dict:
    """Verify Telegram Login Widget callback params. Returns user data dict."""
    if "hash" not in params:
        raise TelegramLoginWidgetError("Missing hash parameter")

    received_hash = params["hash"]
    data_items = {k: v for k, v in params.items() if k != "hash"}

    data_check_string = "\n".join(
        f"{k}={v}" for k, v in sorted(data_items.items())
    )

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    computed_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(computed_hash, received_hash):
        raise TelegramLoginWidgetError("Invalid hash — data tampered")

    auth_date_str = params.get("auth_date", "0")
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        raise TelegramLoginWidgetError("Invalid auth_date")

    now = int(datetime.now(timezone.utc).timestamp())
    if now - auth_date > max_age_seconds:
        raise TelegramLoginWidgetError("Auth data expired")

    return data_items
