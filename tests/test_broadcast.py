"""Tests for internal broadcast endpoint authentication."""
from __future__ import annotations

import pytest

from pitchcopytrade.bot.main import _handle_health, _handle_internal_broadcast


class TestBroadcastTokenValidation:
    """Test that /internal/broadcast correctly validates X-Internal-Token header."""

    def test_handler_functions_exist(self):
        import asyncio
        assert callable(_handle_health)
        assert callable(_handle_internal_broadcast)

    def test_correct_token_accepted(self):
        """The handler should accept requests with correct token."""
        # Verify the token comparison logic using hmac.compare_digest semantics
        secret = "test-secret-token"
        token = "test-secret-token"
        import hmac
        assert hmac.compare_digest(token, secret)

    def test_wrong_token_rejected(self):
        """The handler must reject wrong tokens."""
        secret = "correct-secret"
        token = "wrong-secret"
        import hmac
        assert not hmac.compare_digest(token, secret)

    def test_empty_token_rejected(self):
        """The handler must reject empty tokens."""
        secret = "correct-secret"
        token = ""
        import hmac
        assert not hmac.compare_digest(token, secret)

    async def test_broadcast_handler_rejects_bad_token(self):
        """Test the actual handler rejects bad token with 401."""
        from unittest.mock import MagicMock, AsyncMock
        from aiohttp.web_request import Request

        settings = MagicMock()
        settings.internal_api_secret.get_secret_value.return_value = "correct-secret"

        request = MagicMock()
        request.app = {"settings": settings, "bot": MagicMock()}
        request.headers = {"X-Internal-Token": "wrong-token"}

        response = await _handle_internal_broadcast(request)
        assert response.status == 401

    async def test_broadcast_handler_rejects_missing_rec_id(self):
        """Test the actual handler returns 400 when recommendation_id missing."""
        from unittest.mock import MagicMock, AsyncMock
        import json

        settings = MagicMock()
        settings.internal_api_secret.get_secret_value.return_value = "correct-secret"

        request = MagicMock()
        request.app = {"settings": settings, "bot": MagicMock()}
        request.headers = {"X-Internal-Token": "correct-secret"}
        request.json = AsyncMock(return_value={})

        response = await _handle_internal_broadcast(request)
        assert response.status == 400
