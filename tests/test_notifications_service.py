from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg
from pitchcopytrade.db.models.enums import InstrumentType, RecommendationKind, RecommendationStatus, RiskLevel, StrategyStatus, TradeSide
from pitchcopytrade.services.notifications import _send_with_retry, build_recommendation_notification_text


def test_build_recommendation_notification_text_includes_leg_and_attachments() -> None:
    author_user = User(id="author-user-1", full_name="Alpha Desk")
    author = AuthorProfile(id="author-1", user_id="author-user-1", display_name="Alpha Desk", slug="alpha-desk", is_active=True)
    author.user = author_user
    strategy = Strategy(
        id="strategy-1",
        author_id="author-1",
        slug="momentum-ru",
        title="Momentum RU",
        short_description="desc",
        full_description="full",
        risk_level=RiskLevel.MEDIUM,
        status=StrategyStatus.PUBLISHED,
        min_capital_rub=150000,
        is_public=True,
    )
    strategy.author = author
    recommendation = Recommendation(
        id="rec-1",
        strategy_id="strategy-1",
        author_id="author-1",
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.PUBLISHED,
        title="Покупка SBER",
        summary="Сильный спрос",
        published_at=datetime(2026, 3, 11, tzinfo=timezone.utc),
    )
    recommendation.strategy = strategy
    recommendation.author = author
    instrument = Instrument(
        id="instrument-1",
        ticker="SBER",
        name="Sberbank",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )
    leg = RecommendationLeg(
        id="leg-1",
        recommendation_id="rec-1",
        instrument_id="instrument-1",
        side=TradeSide.BUY,
        entry_from=101.5,
    )
    leg.instrument = instrument
    recommendation.legs = [leg]
    recommendation.attachments = [
        RecommendationAttachment(
            id="att-1",
            recommendation_id="rec-1",
            bucket_name="uploads",
            object_key="recommendations/rec-1/file.pdf",
            original_filename="idea.pdf",
            content_type="application/pdf",
            size_bytes=123,
        )
    ]

    text = build_recommendation_notification_text(recommendation)

    assert "Новая публикация" in text
    assert "Покупка SBER" in text
    assert "SBER buy 101.5" in text
    assert "Вложений: 1" in text


@pytest.mark.asyncio
async def test_send_with_retry_recovers_after_first_failure() -> None:
    send_message = AsyncMock(side_effect=[RuntimeError("temp"), None])

    delivered = await _send_with_retry(send_message, 12345, "hello", attempts=3)

    assert delivered is True
    assert send_message.await_count == 2
