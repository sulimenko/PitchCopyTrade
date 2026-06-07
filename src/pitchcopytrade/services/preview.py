from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from pitchcopytrade.db.models.enums import (
    PaymentStatus,
    ProductType,
    MessageKind,
    MessageStatus,
    RiskLevel,
    StrategyStatus,
    SubscriptionStatus,
    TradeSide,
)


def build_preview_miniapp_context() -> dict[str, object]:
    user = SimpleNamespace(
        id="preview-subscriber",
        telegram_user_id=700000001,
        username="preview_subscriber",
        full_name="Preview Subscriber",
        email="preview.subscriber@example.com",
        timezone="Europe/Moscow",
    )
    author = SimpleNamespace(display_name="Alpha Desk", slug="alpha-desk")
    strategy = _build_preview_strategy(author)
    product = strategy.subscription_products[0]
    payment = SimpleNamespace(
        id="preview-payment-1",
        product=product,
        final_amount_rub=4900,
        discount_rub=0,
        provider="stub_manual",
        status=PaymentStatus.PENDING,
        stub_reference="PREVIEW-001",
        provider_payload={},
        expires_at=None,
        created_at=datetime.now(UTC) - timedelta(hours=2),
        updated_at=datetime.now(UTC) - timedelta(hours=1),
    )
    subscription = SimpleNamespace(
        id="preview-subscription-1",
        product=product,
        status=SubscriptionStatus.ACTIVE,
        is_trial=False,
        start_at=datetime.now(UTC) - timedelta(days=4),
        end_at=datetime.now(UTC) + timedelta(days=26),
        autorenew_enabled=True,
        applied_promo_code=None,
        manual_discount_rub=0,
        payment=payment,
    )
    payment.subscriptions = [subscription]
    snapshot = SimpleNamespace(
        user=user,
        has_access=True,
        subscriptions=[subscription],
        active_subscriptions=[subscription],
        payments=[payment],
        pending_payments=[payment],
        visible_message_titles=[
            "Риск на пробое",
            "Сценарий на импульс",
            "Сработал уровень входа",
        ],
    )
    recommendation = _build_preview_recommendation(strategy)
    return {
        "preview_user": user,
        "preview_strategy": strategy,
        "preview_product": product,
        "preview_snapshot": snapshot,
        "preview_recommendation": recommendation,
    }


def build_preview_admin_context() -> dict[str, object]:
    user = SimpleNamespace(
        id="preview-admin",
        full_name="Preview Admin",
        username="preview_admin",
        email="preview.admin@example.com",
    )
    stats = SimpleNamespace(
        authors_total=4,
        strategies_total=8,
        strategies_public=5,
        active_subscriptions=19,
        messages_live=7,
    )
    recent_strategies = [
        _simple_strategy("trend-ru", "Trend RU", "Импульс на российском рынке", "medium", "Alpha Desk", 150000, True),
        _simple_strategy("value-mid", "Value Mid", "Сценарий на восстановление", "low", "Beta Desk", 100000, False),
    ]
    recent_products = [
        SimpleNamespace(
            id="preview-product-1",
            title="Премиум доступ",
            description="Месячная подписка с быстрым доступом к ленте идей.",
            product_type=ProductType.STRATEGY,
            duration_days=30,
            price_rub=4900,
            trial_days=7,
            is_active=True,
        )
    ]
    recent_subscriptions = [
        SimpleNamespace(
            id="preview-subscription-1",
            user=SimpleNamespace(full_name="Ирина Петрова", email="irina@example.com", id="user-1"),
            product=recent_products[0],
            status=SubscriptionStatus.ACTIVE,
            start_at="2026-03-01",
            end_at="2026-03-31",
            payment=SimpleNamespace(status=PaymentStatus.PAID),
        )
    ]
    recent_payments = [
        SimpleNamespace(
            id="preview-payment-1",
            user=SimpleNamespace(full_name="Ирина Петрова", email="irina@example.com", id="user-1"),
            product=recent_products[0],
            final_amount_rub=4900,
            provider="stub_manual",
            status=PaymentStatus.PENDING,
            stub_reference="PREVIEW-001",
        )
    ]
    return {
        "preview_mode": True,
        "user": user,
        "stats": stats,
        "recent_strategies": recent_strategies,
        "recent_products": recent_products,
        "recent_subscriptions": recent_subscriptions,
        "recent_payments": recent_payments,
    }


def build_preview_author_context() -> dict[str, object]:
    user = SimpleNamespace(
        id="preview-author-user",
        full_name="Preview Author",
        username="preview_author",
        email="preview.author@example.com",
    )
    author = SimpleNamespace(
        id="preview-author",
        display_name="Preview Author Desk",
        slug="preview-author-desk",
        requires_moderation=False,
    )
    strategy_one = _simple_strategy("trend-ru", "Trend RU", "Импульс на российском рынке", "medium", author.display_name, 150000, True)
    strategy_two = _simple_strategy("short-vol", "Short Vol", "Тезис на волатильность", "high", author.display_name, 200000, False)
    recommendation = _build_preview_recommendation(strategy_one)
    stats = SimpleNamespace(
        strategies_total=2,
        messages_total=5,
        draft_messages=1,
        live_messages=2,
    )
    watchlist_items = [
        {"id": "SBER", "ticker": "SBER", "name": "Сбербанк", "board": "TQBR", "currency": "RUB"},
        {"id": "GAZP", "ticker": "GAZP", "name": "Газпром", "board": "TQBR", "currency": "RUB"},
        {"id": "NVTK", "ticker": "NVTK", "name": "НОВАТЭК", "board": "TQBR", "currency": "RUB"},
    ]
    recommendations = [recommendation]
    return {
        "preview_mode": True,
        "user": user,
        "author": author,
        "stats": stats,
        "strategies": [strategy_one, strategy_two],
        "recommendations": recommendations,
        "watchlist_items": watchlist_items,
        "message_modal_url": "/preview/author/messages/preview-recommendation/preview",
    }


def build_preview_message_context() -> dict[str, object]:
    strategy = _build_preview_strategy(SimpleNamespace(display_name="Preview Author Desk", slug="preview-author-desk"))
    recommendation = _build_preview_recommendation(strategy)
    return {
        "preview_mode": True,
        "user": SimpleNamespace(full_name="Preview Author", username="preview_author"),
        "recommendation": recommendation,
        "attachment_download_enabled": False,
    }


def _build_preview_strategy(author: SimpleNamespace) -> SimpleNamespace:
    product = SimpleNamespace(
        id="preview-product-1",
        title="Премиум доступ",
        description="Месячная подписка с быстрым доступом к ленте идей.",
        product_type=ProductType.STRATEGY,
        duration_days=30,
        price_rub=4900,
        trial_days=7,
        is_active=True,
        autorenew_allowed=True,
    )
    strategy = SimpleNamespace(
        id="preview-strategy-1",
        slug="straddle-pro",
        title="Straddle Pro",
        short_description="Структурная стратегия на понятный рыночный сценарий.",
        full_description="Preview: идея, механизм, риск и коммерческий предложение собраны в одном экране.",
        author=author,
        risk_level=RiskLevel.MEDIUM,
        min_capital_rub=150000,
        status=StrategyStatus.PUBLISHED,
        is_public=True,
        subscription_products=[product],
    )
    product.strategy = strategy
    return strategy


def _simple_strategy(
    slug: str,
    title: str,
    short_description: str,
    risk_level: str,
    author_display_name: str,
    min_capital_rub: int,
    is_public: bool,
) -> SimpleNamespace:
    author = SimpleNamespace(display_name=author_display_name, slug=author_display_name.lower().replace(" ", "-"))
    return SimpleNamespace(
        id=f"preview-{slug}",
        slug=slug,
        title=title,
        short_description=short_description,
        full_description=f"Preview content for {title}.",
        author=author,
        risk_level=risk_level,
        min_capital_rub=min_capital_rub,
        status=StrategyStatus.PUBLISHED,
        is_public=is_public,
        subscription_products=[
            SimpleNamespace(
                id=f"preview-product-{slug}",
                title="Премиум доступ",
                description="Месячная подписка с быстрым доступом к ленте идей.",
                product_type=ProductType.STRATEGY,
                duration_days=30,
                price_rub=4900,
                trial_days=7,
                is_active=True,
                autorenew_allowed=True,
            )
        ],
    )


def _build_preview_recommendation(strategy: SimpleNamespace) -> SimpleNamespace:
    payload = {
        "mode": "structured",
        "instrument_id": "SBER",
        "side": "buy",
        "price": "250.10",
        "quantity": "100",
        "amount": "25010",
        "title": "Риск на пробое",
    }
    return SimpleNamespace(
        id="preview-recommendation",
        title="Риск на пробое",
        message_payload=payload,
        created_at=datetime.now(UTC) - timedelta(days=1),
        updated_at=datetime.now(UTC),
        kind=MessageKind.IDEA,
        status=MessageStatus.PUBLISHED,
        strategy=strategy,
        legs=[
            SimpleNamespace(
                instrument=SimpleNamespace(ticker="SBER"),
                side=TradeSide.BUY,
                entry_from="250.10",
                take_profit_1="262.40",
                stop_loss="244.80",
            )
        ],
        messages=[
            SimpleNamespace(
                mode="structured",
                body="Structured recommendation · instrument=SBER · side=buy · price=250.10 · qty=100 · amount=25010",
                payload=payload,
                created_at=datetime.now(UTC) - timedelta(days=1),
            )
        ],
        attachments=[],
    )
