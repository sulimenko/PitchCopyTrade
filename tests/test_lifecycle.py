from __future__ import annotations

from datetime import datetime, timezone
import json

import pytest

from pitchcopytrade.db.models.enums import PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.lifecycle import expire_due_payments, expire_due_subscriptions


def _write_runtime_dataset(store: FileDataStore) -> None:
    store.root_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "roles": [],
        "users": [
            {
                "id": "user-1",
                "email": "lead@example.com",
                "full_name": "Lead User",
                "username": "lead",
                "password_hash": None,
                "telegram_user_id": 1001,
                "status": "active",
                "timezone": "Europe/Moscow",
                "lead_source_id": None,
            }
        ],
        "authors": [],
        "bundles": [],
        "strategies": [],
        "products": [
            {
                "id": "product-1",
                "product_type": "strategy",
                "slug": "momentum-ru-month",
                "title": "Momentum RU",
                "description": "Monthly",
                "strategy_id": None,
                "author_id": None,
                "bundle_id": None,
                "duration_days": 30,
                "price_rub": 499,
                "trial_days": 0,
                "is_active": True,
                "autorenew_allowed": True,
            }
        ],
        "lead_sources": [],
        "legal_documents": [],
        "promo_codes": [],
        "payments": [
            {
                "id": "payment-1",
                "user_id": "user-1",
                "product_id": "product-1",
                "promo_code_id": None,
                "provider": "stub_manual",
                "status": "pending",
                "amount_rub": 499,
                "discount_rub": 0,
                "final_amount_rub": 499,
                "currency": "RUB",
                "stub_reference": "MANUAL-1",
                "external_id": None,
                "provider_payload": {},
                "confirmed_at": None,
                "expires_at": "2026-03-01T10:00:00+00:00",
            }
        ],
        "subscriptions": [
            {
                "id": "subscription-1",
                "user_id": "user-1",
                "product_id": "product-1",
                "payment_id": "payment-1",
                "lead_source_id": None,
                "status": "pending",
                "autorenew_enabled": True,
                "is_trial": False,
                "applied_promo_code_id": None,
                "manual_discount_rub": 0,
                "start_at": "2026-03-01T10:00:00+00:00",
                "end_at": "2026-03-15T10:00:00+00:00",
            },
            {
                "id": "subscription-2",
                "user_id": "user-1",
                "product_id": "product-1",
                "payment_id": None,
                "lead_source_id": None,
                "status": "active",
                "autorenew_enabled": True,
                "is_trial": False,
                "applied_promo_code_id": None,
                "manual_discount_rub": 0,
                "start_at": "2026-02-01T10:00:00+00:00",
                "end_at": "2026-03-01T10:00:00+00:00",
            },
        ],
        "user_consents": [],
        "recommendations": [],
        "messages": [],
        "audit_events": [],
    }
    for name, data in payload.items():
        store.save_dataset(name, data)


@pytest.mark.asyncio
async def test_expire_due_payments_updates_payment_and_subscription(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "seed")
    _write_runtime_dataset(store)

    stats = await expire_due_payments(None, now=datetime(2026, 3, 12, tzinfo=timezone.utc), store=store)
    payments = {item["id"]: item for item in json.loads((store.root_dir / "payments.json").read_text())}
    subscriptions = {item["id"]: item for item in json.loads((store.root_dir / "subscriptions.json").read_text())}

    assert stats.expired == 1
    assert stats.cancelled == 1
    assert payments["payment-1"]["status"] == PaymentStatus.EXPIRED.value
    assert subscriptions["subscription-1"]["status"] == SubscriptionStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_expire_due_subscriptions_updates_runtime_status(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "runtime", seed_dir=tmp_path / "seed")
    _write_runtime_dataset(store)

    stats = await expire_due_subscriptions(None, now=datetime(2026, 3, 12, tzinfo=timezone.utc), store=store)
    subscriptions = {item["id"]: item for item in json.loads((store.root_dir / "subscriptions.json").read_text())}

    assert stats.expired == 1
    assert subscriptions["subscription-2"]["status"] == SubscriptionStatus.EXPIRED.value
    assert subscriptions["subscription-2"]["autorenew_enabled"] is False
