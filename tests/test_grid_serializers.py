from __future__ import annotations

from types import SimpleNamespace

import json

from pitchcopytrade.api.routes._grid_serializers import (
    serialize_author_strategies,
    serialize_delivery,
    serialize_moderation_queue,
    serialize_payments,
    serialize_recommendations,
    serialize_strategies,
    serialize_subscriptions,
)


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def test_grid_serializers_use_russian_labels() -> None:
    strategy = _ns(
        id="strategy-1",
        title="Momentum RU",
        slug="momentum-ru",
        author=_ns(display_name="Alpha Desk"),
        risk_level="LOW",
        status="ACTIVE",
        is_public=True,
        min_capital_rub=150000,
    )
    subscription = _ns(
        id="subscription-1",
        status="ACTIVE",
        start_at=None,
        end_at=None,
        user=_ns(full_name="Lead User", email="lead@example.com", username="lead"),
        product=_ns(title="Momentum RU Monthly"),
        lead_source=_ns(name="Telegram Organic", ref_code="tg-organic", source_type="ORGANIC"),
    )
    payment = _ns(
        id="payment-1",
        status="CONFIRMED",
        provider="stub_manual",
        user=_ns(full_name="Lead User", email="lead@example.com", username="lead"),
        product=_ns(title="Momentum RU Monthly"),
        subscriptions=[],
        stub_reference="REF-1",
        external_id=None,
        final_amount_rub=4900,
    )
    message = _ns(
        id="msg-1",
        title="Покупка SBER",
        type="TEXT",
        status="PUBLISHED",
        strategy=_ns(title="Momentum RU"),
        text={"plain": "Сильный спрос"},
        comment="",
        deliver=["strategy"],
        documents=[],
        deals=[],
        updated=None,
    )
    author_strategy = _ns(
        id="strategy-2",
        title="Momentum RX",
        slug="momentum-rx",
        short_description="desc",
        risk_level="MEDIUM",
        status="ACTIVE",
        min_capital_rub=200000,
    )
    moderation_item = _ns(
        id="msg-2",
        title="Сигнал",
        kind="IDEA",
        status="REVIEW",
        type="MIXED",
        text={"plain": "Текст"},
        comment="",
        strategy=_ns(title="Momentum RU", author=_ns(display_name="Alpha Desk")),
        author=None,
    )
    delivery_record = _ns(
        message=_ns(id="msg-3", title="Покупка SBER", strategy=_ns(title="Momentum RU"), author=_ns(display_name="Alpha Desk")),
        delivered_recipients=1,
        delivery_attempts=1,
        latest_delivery_event=_ns(created_at=None, payload={}),
    )

    strategies_json = json.loads(serialize_strategies([strategy]))
    subscriptions_json = json.loads(serialize_subscriptions([subscription]))
    payments_json = json.loads(serialize_payments([payment]))
    recommendations_json = json.loads(serialize_recommendations([message]))
    author_strategies_json = json.loads(serialize_author_strategies([author_strategy]))
    moderation_json = json.loads(serialize_moderation_queue([moderation_item]))
    delivery_json = json.loads(serialize_delivery([delivery_record]))

    assert "Низкий" in strategies_json[0]["risk"]
    assert "Активен" in strategies_json[0]["status"]
    assert "Активен" in subscriptions_json[0]["status"]
    assert "Telegram Organic" in subscriptions_json[0]["source"]
    assert "Оплачен" in payments_json[0]["status"]
    assert "Текст" in recommendations_json[0]["type"]
    assert "Опубликовано" in recommendations_json[0]["status"]
    assert "Средний" in author_strategies_json[0]["risk"]
    assert "Активен" in author_strategies_json[0]["status"]
    assert "Идея" in moderation_json[0]["kind"]
    assert "На модерации" in moderation_json[0]["status"]
    assert "Доставлено" in delivery_json[0]["status"]
