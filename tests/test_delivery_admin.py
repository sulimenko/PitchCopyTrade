from __future__ import annotations

from pathlib import Path
from shutil import copytree

import pytest

from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.delivery_admin import get_admin_delivery_record, retry_recommendation_delivery


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
    notifier = DummyNotifier()

    record = await retry_recommendation_delivery(None, "rec-1", notifier, store=store)
    loaded = await get_admin_delivery_record(None, "rec-1", store=store)

    assert notifier.chat_ids == [222]
    assert record.delivery_attempts == 1
    assert record.latest_delivery_event is not None
    assert record.latest_delivery_event.payload["trigger"] == "manual_retry"
    assert loaded is not None
    assert loaded.delivery_attempts == 1
