"""Tests for Telegram Login Widget auth and role-based access control."""
from __future__ import annotations

import hashlib
import hmac
import time

import pytest
from fastapi.testclient import TestClient

from pitchcopytrade.auth.telegram_login_widget import TelegramLoginWidgetError, verify_telegram_login_widget


BOT_TOKEN = "test_bot_token_123"


def _make_valid_params(bot_token: str = BOT_TOKEN, offset_seconds: int = 0) -> dict:
    auth_date = int(time.time()) - offset_seconds
    params = {
        "id": "123456789",
        "first_name": "Test",
        "auth_date": str(auth_date),
    }
    data_check = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hashlib.sha256(bot_token.encode()).digest()
    hash_val = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    params["hash"] = hash_val
    return params


class TestTelegramLoginWidget:
    def test_valid_params(self):
        params = _make_valid_params()
        result = verify_telegram_login_widget(params, BOT_TOKEN, max_age_seconds=300)
        assert result["id"] == "123456789"
        assert "hash" not in result

    def test_tampered_data(self):
        params = _make_valid_params()
        params["id"] = "999999999"
        with pytest.raises(TelegramLoginWidgetError, match="Invalid hash"):
            verify_telegram_login_widget(params, BOT_TOKEN)

    def test_missing_hash(self):
        params = {"id": "123", "auth_date": str(int(time.time()))}
        with pytest.raises(TelegramLoginWidgetError, match="Missing hash"):
            verify_telegram_login_widget(params, BOT_TOKEN)

    def test_expired_auth_date(self):
        params = _make_valid_params(offset_seconds=400)
        with pytest.raises(TelegramLoginWidgetError, match="expired"):
            verify_telegram_login_widget(params, BOT_TOKEN, max_age_seconds=300)

    def test_wrong_bot_token(self):
        params = _make_valid_params(bot_token=BOT_TOKEN)
        with pytest.raises(TelegramLoginWidgetError, match="Invalid hash"):
            verify_telegram_login_widget(params, "wrong_token_here")


class TestProtectedRoutes:
    def _make_client(self) -> TestClient:
        from pitchcopytrade.api.main import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_admin_requires_auth(self):
        with self._make_client() as client:
            response = client.get("/admin/dashboard", follow_redirects=False)
            assert response.status_code in (401, 403, 307, 302)

    def test_cabinet_requires_auth(self):
        with self._make_client() as client:
            response = client.get("/cabinet/strategies", follow_redirects=False)
            assert response.status_code in (401, 403, 307, 302)

    def test_login_page_accessible(self):
        with self._make_client() as client:
            response = client.get("/login")
            assert response.status_code == 200
