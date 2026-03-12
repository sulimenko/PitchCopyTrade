from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.enums import PaymentStatus, SubscriptionStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.payment_sync import process_tbank_callback, sync_tbank_pending_payments


class DummyTBankClient:
    def __init__(self, state_by_payment_id: dict[str, dict[str, object]]) -> None:
        self.state_by_payment_id = state_by_payment_id

    async def get_state(self, *, payment_id: str) -> dict[str, object]:
        return self.state_by_payment_id[payment_id]


def _seed_tbank_pending_checkout(store: FileDataStore) -> None:
    now = datetime(2026, 3, 12, tzinfo=timezone.utc).isoformat()
    store.save_many(
        {
            "roles": [],
            "users": [
                {
                    "id": "user-sub",
                    "email": "sub@example.com",
                    "telegram_user_id": 222,
                    "username": "sub1",
                    "full_name": "Subscriber One",
                    "password_hash": None,
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": [],
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "authors": [],
            "lead_sources": [],
            "instruments": [],
            "strategies": [],
            "bundles": [],
            "bundle_members": [],
            "products": [
                {
                    "id": "product-1",
                    "product_type": "strategy",
                    "slug": "momentum-ru-month",
                    "title": "Momentum RU Monthly",
                    "description": None,
                    "strategy_id": None,
                    "author_id": None,
                    "bundle_id": None,
                    "billing_period": "month",
                    "price_rub": 4900,
                    "trial_days": 7,
                    "is_active": True,
                    "autorenew_allowed": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "legal_documents": [],
            "payments": [
                {
                    "id": "payment-1",
                    "user_id": "user-sub",
                    "product_id": "product-1",
                    "promo_code_id": None,
                    "provider": "tbank",
                    "status": "pending",
                    "amount_rub": 4900,
                    "discount_rub": 0,
                    "final_amount_rub": 4900,
                    "currency": "RUB",
                    "external_id": "777",
                    "stub_reference": "MANUAL-MOMENTUM-ABCD1234",
                    "provider_payload": {"provider_payment_id": "777"},
                    "expires_at": None,
                    "confirmed_at": None,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "subscriptions": [
                {
                    "id": "sub-1",
                    "user_id": "user-sub",
                    "product_id": "product-1",
                    "payment_id": "payment-1",
                    "lead_source_id": None,
                    "applied_promo_code_id": None,
                    "status": "pending",
                    "autorenew_enabled": True,
                    "is_trial": True,
                    "manual_discount_rub": 0,
                    "start_at": now,
                    "end_at": datetime(2026, 4, 12, tzinfo=timezone.utc).isoformat(),
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "user_consents": [],
            "audit_events": [],
            "recommendations": [],
            "recommendation_legs": [],
            "recommendation_attachments": [],
        }
    )


@pytest.mark.asyncio
async def test_sync_tbank_pending_payments_marks_confirmed_payment_paid(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path)
    _seed_tbank_pending_checkout(store)

    stats = await sync_tbank_pending_payments(
        None,
        client=DummyTBankClient(
            {
                "777": {
                    "Success": True,
                    "PaymentId": "777",
                    "Status": "CONFIRMED",
                }
            }
        ),
        now=datetime(2026, 3, 12, 12, tzinfo=timezone.utc),
        store=store,
    )

    graph = FileDatasetGraph.load(store)
    payment = graph.payments["payment-1"]
    subscription = graph.subscriptions["sub-1"]

    assert stats.checked == 1
    assert stats.paid == 1
    assert payment.status == PaymentStatus.PAID
    assert subscription.status == SubscriptionStatus.TRIAL
    assert payment.provider_payload["last_state"]["Status"] == "CONFIRMED"
    assert any(event.action == "worker.payment_state_sync" for event in graph.audit_events.values())


@pytest.mark.asyncio
async def test_sync_tbank_pending_payments_marks_rejected_payment_failed(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path)
    _seed_tbank_pending_checkout(store)

    stats = await sync_tbank_pending_payments(
        None,
        client=DummyTBankClient(
            {
                "777": {
                    "Success": True,
                    "PaymentId": "777",
                    "Status": "REJECTED",
                }
            }
        ),
        now=datetime(2026, 3, 12, 12, tzinfo=timezone.utc),
        store=store,
    )

    graph = FileDatasetGraph.load(store)
    payment = graph.payments["payment-1"]
    subscription = graph.subscriptions["sub-1"]

    assert stats.checked == 1
    assert stats.failed == 1
    assert payment.status == PaymentStatus.FAILED
    assert subscription.status == SubscriptionStatus.CANCELLED


@pytest.mark.asyncio
async def test_process_tbank_callback_marks_payment_paid_in_file_mode(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path)
    _seed_tbank_pending_checkout(store)

    result = await process_tbank_callback(
        None,
        payload={"TerminalKey": "term", "PaymentId": "777", "Status": "CONFIRMED"},
        now=datetime(2026, 3, 12, 13, tzinfo=timezone.utc),
        store=store,
    )

    graph = FileDatasetGraph.load(store)
    payment = graph.payments["payment-1"]
    subscription = graph.subscriptions["sub-1"]

    assert result.found is True
    assert result.changed is True
    assert payment.status == PaymentStatus.PAID
    assert subscription.status == SubscriptionStatus.TRIAL
    assert any(event.action == "payment.webhook_sync" for event in graph.audit_events.values())
