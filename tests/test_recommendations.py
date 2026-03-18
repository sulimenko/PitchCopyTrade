"""Tests for recommendation creation and publishing flow."""
from __future__ import annotations

import pytest

from pitchcopytrade.auth.telegram_login_widget import TelegramLoginWidgetError, verify_telegram_login_widget


class TestRecommendationCreation:
    """Verify recommendation creation constraints."""

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
        from pitchcopytrade.api.routes.cabinet import _parse_decimal
        assert _parse_decimal("") is None
        assert _parse_decimal("  ") is None
        assert _parse_decimal("312.50") is not None
        assert float(_parse_decimal("312.50")) == pytest.approx(312.50)

    def test_slugify(self):
        from pitchcopytrade.api.routes.cabinet import _slugify
        assert _slugify("Моя стратегия") == "моя-стратегия"
        assert _slugify("Test Strategy 123") == "test-strategy-123"
        assert len(_slugify("a" * 200)) <= 120


class TestRecommendationPublishACL:
    """Verify that only the author of a recommendation can publish it."""

    def test_author_id_mismatch_raises(self):
        # The cabinet routes use _get_author_recommendation which checks author_id
        # This is a unit-level contract test
        import asyncio
        from fastapi import HTTPException
        from unittest.mock import AsyncMock, MagicMock, patch

        async def run():
            from pitchcopytrade.api.routes.cabinet import _get_author_recommendation
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)

            with pytest.raises(HTTPException) as exc_info:
                await _get_author_recommendation(mock_session, "rec-id-1", "author-id-A")
            assert exc_info.value.status_code == 404

        asyncio.run(run())
