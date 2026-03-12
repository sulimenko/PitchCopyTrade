from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.notifications import deliver_subscriber_reminders


class DummyNotifier:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str):
        self.sent.append((chat_id, text))


def _seed_reminder_graph(store: FileDataStore) -> None:
    now = datetime(2026, 3, 12, tzinfo=timezone.utc)
    store.save_many(
        {
            "roles": [],
            "users": [
                {
                    "id": "user-1",
                    "email": "sub@example.com",
                    "telegram_user_id": 222,
                    "username": "sub1",
                    "full_name": "Subscriber One",
                    "password_hash": None,
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": [],
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
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
                    "title": "Momentum RU",
                    "description": None,
                    "strategy_id": None,
                    "author_id": None,
                    "bundle_id": None,
                    "billing_period": "month",
                    "price_rub": 499,
                    "trial_days": 7,
                    "is_active": True,
                    "autorenew_allowed": True,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            ],
            "promo_codes": [],
            "legal_documents": [],
            "payments": [
                {
                    "id": "payment-1",
                    "user_id": "user-1",
                    "product_id": "product-1",
                    "promo_code_id": None,
                    "provider": "tbank",
                    "status": "pending",
                    "amount_rub": 499,
                    "discount_rub": 0,
                    "final_amount_rub": 499,
                    "currency": "RUB",
                    "external_id": "tb-1",
                    "stub_reference": "TB-1",
                    "provider_payload": {},
                    "expires_at": (now + timedelta(hours=2)).isoformat(),
                    "confirmed_at": None,
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }
            ],
            "subscriptions": [
                {
                    "id": "sub-1",
                    "user_id": "user-1",
                    "product_id": "product-1",
                    "payment_id": "payment-1",
                    "lead_source_id": None,
                    "applied_promo_code_id": None,
                    "status": "active",
                    "autorenew_enabled": True,
                    "is_trial": False,
                    "manual_discount_rub": 0,
                    "start_at": now.isoformat(),
                    "end_at": (now + timedelta(days=1)).isoformat(),
                    "created_at": now.isoformat(),
                    "updated_at": now.isoformat(),
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
async def test_deliver_subscriber_reminders_file_sends_and_dedups(tmp_path: Path) -> None:
    store = FileDataStore(root_dir=tmp_path)
    _seed_reminder_graph(store)
    notifier = DummyNotifier()
    now = datetime(2026, 3, 12, 12, tzinfo=timezone.utc)

    first = await deliver_subscriber_reminders(None, notifier, now=now, store=store)
    second = await deliver_subscriber_reminders(None, notifier, now=now, store=store)

    graph = FileDatasetGraph.load(store)

    assert first.sent == 2
    assert second.sent == 0
    assert second.skipped == 2
    assert len(notifier.sent) == 2
    assert any("Скоро закончится подписка" in text for _, text in notifier.sent)
    assert any("Оплата ожидает завершения" in text for _, text in notifier.sent)
    assert sum(1 for event in graph.audit_events.values() if event.action == "notification.reminder") == 2
