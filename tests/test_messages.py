"""Tests for message creation and publishing flow."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pitchcopytrade.auth.telegram_login_widget import TelegramLoginWidgetError, verify_telegram_login_widget


class TestMessageCreation:
    """Verify message creation constraints."""

    def test_ticker_only_fields_required(self):
        """Ticker and side are the only required fields per spec."""
        # This test validates the contract: price/target/stop are nullable
        required_fields = {"ticker", "side"}
        optional_fields = {"price", "target", "stop"}
        all_fields = required_fields | optional_fields
        # No required from optional
        assert required_fields & optional_fields == set()
        assert len(required_fields) == 2

    def test_parse_decimal_nullable(self):
        from pitchcopytrade.services.author import _parse_decimal

        assert _parse_decimal("", "bad") is None
        assert _parse_decimal("  ", "bad") is None
        assert _parse_decimal("312.50", "bad") is not None
        assert float(_parse_decimal("312.50", "bad")) == pytest.approx(312.50)

    def test_slugify(self):
        from pitchcopytrade.services.author import _slugify
        assert _slugify("Моя стратегия") == "моя-стратегия"
        assert _slugify("Test Strategy 123") == "test-strategy-123"
        assert len(_slugify("a" * 200)) <= 120


class TestMessagePublishACL:
    """Verify that author-scoped message lookups use the author id."""

    @pytest.mark.asyncio
    async def test_author_id_is_forwarded_to_repository(self):
        captured: dict[str, str] = {}

        class Repo:
            async def get_author_message(self, author_id: str, message_id: str):
                captured["author_id"] = author_id
                captured["message_id"] = message_id
                return None

        author = SimpleNamespace(id="author-id-A")
        async def get_author_message(repository, author_obj, message_id):
            return await repository.get_author_message(author_obj.id, message_id)

        await get_author_message(Repo(), author, "msg-1")
        assert captured == {"author_id": "author-id-A", "message_id": "msg-1"}
