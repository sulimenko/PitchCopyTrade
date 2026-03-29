from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest

from datetime import datetime, timezone

from pitchcopytrade.db.models.enums import MessageStatus
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.delivery_admin import (
    get_admin_delivery_record,
    list_admin_delivery_records,
    retry_message_delivery,
)


class DummyNotifier:
    def __init__(self) -> None:
        self.chat_ids: list[int] = []

    async def send_message(self, chat_id: int, text: str) -> None:
        self.chat_ids.append(chat_id)


@pytest.mark.asyncio
async def test_file_mode_retry_delivery_writes_audit_event(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    copytree(project_root / "storage" / "seed" / "json", tmp_path / "storage" / "seed" / "json")
    copytree(project_root / "storage" / "seed" / "blob", tmp_path / "storage" / "seed" / "blob")

    store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )
    graph = FileDatasetGraph.load(store)
    graph.messages["message-1"].status = MessageStatus.PUBLISHED
    graph.messages["message-1"].published = datetime(2026, 3, 11, tzinfo=timezone.utc)
    graph.save(store)
    notifier = DummyNotifier()

    record = await retry_message_delivery(None, "message-1", notifier, store=store)
    loaded = await get_admin_delivery_record(None, "message-1", store=store)

    assert notifier.chat_ids == [222]
    assert record.delivery_attempts == 1
    assert record.latest_delivery_event is not None
    assert record.latest_delivery_event.payload["trigger"] == "manual_retry"
    assert loaded is not None
    assert loaded.delivery_attempts == 1


@pytest.mark.asyncio
async def test_file_mode_list_delivery_records_uses_message_events(tmp_path: Path) -> None:
    project_root = Path(__file__).resolve().parents[1]
    copytree(project_root / "storage" / "seed" / "json", tmp_path / "storage" / "seed" / "json")
    copytree(project_root / "storage" / "seed" / "blob", tmp_path / "storage" / "seed" / "blob")

    store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )
    graph = FileDatasetGraph.load(store)
    graph.messages["message-1"].status = MessageStatus.PUBLISHED
    graph.messages["message-1"].published = datetime(2026, 3, 11, tzinfo=timezone.utc)
    graph.save(store)

    records = await list_admin_delivery_records(None, store=store)

    assert records
    record = next(item for item in records if item.message.id == "message-1")
    assert record.delivery_attempts == 0
