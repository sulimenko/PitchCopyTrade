from __future__ import annotations

from datetime import datetime, timezone

from pitchcopytrade.db.models.content import Message
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


def _seed_message_graph(store: FileDataStore) -> None:
    now = datetime(2026, 3, 11, tzinfo=timezone.utc).isoformat()
    store.save_many(
        {
            "roles": [
                {"id": "role-author", "slug": "author", "title": "Author", "created_at": now, "updated_at": now},
                {"id": "role-admin", "slug": "admin", "title": "Admin", "created_at": now, "updated_at": now},
            ],
            "users": [
                {
                    "id": "user-author",
                    "email": "author@example.com",
                    "telegram_user_id": 111,
                    "username": "author1",
                    "full_name": "Author One",
                    "password_hash": "hash",
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": ["role-author"],
                    "created_at": now,
                    "updated_at": now,
                },
                {
                    "id": "user-subscriber",
                    "email": "subscriber@example.com",
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
                },
                {
                    "id": "user-moderator",
                    "email": "moderator@example.com",
                    "telegram_user_id": 333,
                    "username": "mod1",
                    "full_name": "Moderator One",
                    "password_hash": None,
                    "status": "active",
                    "timezone": "Europe/Moscow",
                    "lead_source_id": None,
                    "role_ids": ["role-admin"],
                    "created_at": now,
                    "updated_at": now,
                },
            ],
            "authors": [
                {
                    "id": "author-1",
                    "user_id": "user-author",
                    "display_name": "Author One",
                    "slug": "author-one",
                    "bio": None,
                    "requires_moderation": False,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "lead_sources": [],
            "instruments": [],
            "strategies": [
                {
                    "id": "strategy-1",
                    "author_id": "author-1",
                    "slug": "momentum-ru",
                    "title": "Momentum RU",
                    "short_description": "desc",
                    "full_description": "full",
                    "risk_level": "medium",
                    "status": "published",
                    "min_capital_rub": 150000,
                    "is_public": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "bundles": [
                {
                    "id": "bundle-1",
                    "slug": "core-alpha",
                    "title": "Core Alpha",
                    "description": "Bundle",
                    "is_public": True,
                    "is_active": True,
                    "created_at": now,
                    "updated_at": now,
                }
            ],
            "bundle_members": [],
            "products": [],
            "promo_codes": [],
            "legal_documents": [],
            "payments": [],
            "subscriptions": [],
            "user_consents": [],
            "audit_events": [],
            "messages": [
                {
                    "id": "message-1",
                    "thread": None,
                    "parent": None,
                    "author": "author-1",
                    "user": "user-subscriber",
                    "moderator": "user-moderator",
                    "strategy": "strategy-1",
                    "bundle": "bundle-1",
                    "deliver": ["telegram"],
                    "channel": ["telegram", "miniapp"],
                    "kind": "new_idea",
                    "type": "structured",
                    "status": "draft",
                    "moderation": "required",
                    "title": "Покупка SBER",
                    "comment": "Первый structured draft",
                    "schedule": None,
                    "published": None,
                    "archived": None,
                    "documents": [{"filename": "idea.pdf"}],
                    "text": {"body": "Текст сообщения"},
                    "deals": [{"instrument": "SBER", "side": "buy"}],
                    "created": now,
                    "updated": now,
                }
            ],
        }
    )


def test_file_data_store_bootstraps_runtime_from_seed(tmp_path) -> None:
    seed_store = FileDataStore(root_dir=tmp_path / "storage" / "seed" / "json", seed_dir=tmp_path / "storage" / "seed" / "json")
    _seed_message_graph(seed_store)

    runtime_store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )

    messages = runtime_store.load_dataset("messages")

    assert len(messages) == 1
    assert messages[0]["title"] == "Покупка SBER"
    assert (tmp_path / "storage" / "runtime" / "json" / "messages.json").exists()


def test_file_dataset_graph_loads_messages_and_relations(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_message_graph(store)

    graph = FileDatasetGraph.load(store)
    message = graph.messages["message-1"]

    assert message.author is graph.authors["author-1"]
    assert message.user is graph.users["user-subscriber"]
    assert message.moderator is graph.users["user-moderator"]
    assert message.strategy is graph.strategies["strategy-1"]
    assert message.bundle is graph.bundles["bundle-1"]
    assert graph.authors["author-1"].messages[0].id == "message-1"
    assert graph.users["user-subscriber"].messages[0].id == "message-1"
    assert graph.users["user-moderator"].moderated_messages[0].id == "message-1"
    assert graph.strategies["strategy-1"].messages[0].id == "message-1"
    assert graph.bundles["bundle-1"].messages[0].id == "message-1"


def test_file_dataset_graph_persists_new_message(tmp_path) -> None:
    store = FileDataStore(root_dir=tmp_path / "storage" / "json")
    _seed_message_graph(store)

    graph = FileDatasetGraph.load(store)
    graph.add(
        Message(
            author_id="author-1",
            user_id="user-subscriber",
            moderator_id="user-moderator",
            strategy_id="strategy-1",
            bundle_id="bundle-1",
            deliver=["telegram"],
            channel=["telegram", "miniapp"],
            kind="update",
            type="text",
            status="draft",
            moderation="required",
            title="Обновление позиции",
            comment="Новое сообщение",
            documents=[],
            text={"body": "Пересобрал вход"},
            deals=[],
        )
    )
    graph.save(store)

    persisted_messages = store.load_dataset("messages")
    assert len(persisted_messages) == 2
    assert any(item["title"] == "Обновление позиции" for item in persisted_messages)

    reloaded = FileDatasetGraph.load(store)
    assert any(item.title == "Обновление позиции" for item in reloaded.messages.values())
