"""Tests for Telegram Login Widget auth and role-based access control."""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from pitchcopytrade.auth.telegram_login_widget import TelegramLoginWidgetError, verify_telegram_login_widget
from pitchcopytrade.auth.telegram_webapp import validate_telegram_webapp_init_data


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

    def test_valid_params_with_extra_fields(self):
        params = _make_valid_params()
        params["photo_url"] = "https://t.me/i/userpic/320/demo.jpg"
        data_items = {k: v for k, v in params.items() if k != "hash"}
        data_check = "\n".join(f"{k}={v}" for k, v in sorted(data_items.items()))
        secret = hashlib.sha256(BOT_TOKEN.encode()).digest()
        params["hash"] = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()

        result = verify_telegram_login_widget(params, BOT_TOKEN, max_age_seconds=300)
        assert result["photo_url"].startswith("https://")

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

    def test_validate_webapp_init_data_accepts_signature_field(self):
        bot_token = "123456:ABC"
        fields = {
            "auth_date": str(int(time.time())),
            "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
            "signature": "signature-value",
            "user": '{"id":123,"first_name":"Test","username":"tester"}',
        }
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted({k: v for k, v in fields.items() if k != "signature"}.items())
        )
        secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        correct_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        init_data = urlencode({**fields, "hash": correct_hash})

        result = validate_telegram_webapp_init_data(init_data, bot_token=bot_token, max_age_seconds=3600)

        assert result["user"].startswith("{\"id\":123")
        assert "signature" not in result

    def test_validate_webapp_init_data_logs_both_hash_variants(self, caplog: pytest.LogCaptureFixture):
        bot_token = "123456:ABC"
        fields = {
            "auth_date": str(int(time.time())),
            "query_id": "AAHdF6IQAAAAAN0XohDhrOrc",
            "signature": "signature-value",
            "user": '{"id":123,"first_name":"Test","username":"tester"}',
        }
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted({k: v for k, v in fields.items() if k != "signature"}.items())
        )
        secret = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        correct_hash = hmac.new(secret, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        init_data = urlencode({**fields, "hash": correct_hash})

        caplog.set_level(logging.DEBUG, logger="pitchcopytrade.auth.telegram_webapp")
        result = validate_telegram_webapp_init_data(init_data, bot_token=bot_token, max_age_seconds=3600)

        assert result["user"].startswith("{\"id\":123")
        debug_messages = [record.getMessage() for record in caplog.records if record.name == "pitchcopytrade.auth.telegram_webapp"]
        assert any("initData validation keys=" in message for message in debug_messages)
        assert any("had_signature=True" in message for message in debug_messages)
        assert any("match_without_signature=True" in message for message in debug_messages)
        assert any("match_with_signature=False" in message for message in debug_messages)
        assert any("bot_token_fingerprint=" in message for message in debug_messages)


class TestProtectedRoutes:
    def _make_client(self) -> TestClient:
        from pitchcopytrade.api.main import create_app
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_admin_requires_auth(self):
        with self._make_client() as client:
            response = client.get("/admin/dashboard", follow_redirects=False)
            assert response.status_code in (401, 403, 307, 302)

    def test_author_requires_auth(self):
        with self._make_client() as client:
            response = client.get("/author/strategies", follow_redirects=False)
            assert response.status_code in (401, 403, 307, 302)

    def test_login_page_accessible(self):
        with self._make_client() as client:
            response = client.get("/login")
            assert response.status_code == 200

    def test_cabinet_routes_removed(self):
        with self._make_client() as client:
            response = client.get("/cabinet/strategies", follow_redirects=False)
            assert response.status_code == 404
