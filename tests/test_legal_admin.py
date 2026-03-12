from __future__ import annotations

from pathlib import Path

import pytest

from pitchcopytrade.db.models.enums import LegalDocumentType
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.legal_admin import (
    LegalDocumentFormData,
    activate_admin_legal_document,
    create_admin_legal_document,
    get_admin_legal_document,
    list_admin_legal_documents,
    update_admin_legal_document,
)
from pitchcopytrade.storage.local import LocalFilesystemStorage


@pytest.mark.asyncio
async def test_file_mode_legal_admin_persists_local_markdown_and_activation(tmp_path: Path) -> None:
    store = FileDataStore(
        root_dir=tmp_path / "storage" / "runtime" / "json",
        seed_dir=tmp_path / "storage" / "seed" / "json",
    )
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "runtime" / "blob")

    created = await create_admin_legal_document(
        None,
        LegalDocumentFormData(
            document_type=LegalDocumentType.OFFER,
            version="v2",
            title="offer v2",
            content_md="# offer\nbody",
        ),
        store=store,
        storage=storage,
    )

    assert created.is_active is False
    assert created.source_path == "legal/offer/v2.md"
    assert (tmp_path / "storage" / "runtime" / "blob" / "legal" / "offer" / "v2.md").read_text(encoding="utf-8") == "# offer\nbody"

    updated = await update_admin_legal_document(
        None,
        created,
        LegalDocumentFormData(
            document_type=LegalDocumentType.OFFER,
            version="v2",
            title="offer v2 updated",
            content_md="# offer\nupdated body",
        ),
        store=store,
        storage=storage,
    )

    assert updated.title == "offer v2 updated"
    assert (tmp_path / "storage" / "runtime" / "blob" / "legal" / "offer" / "v2.md").read_text(encoding="utf-8") == "# offer\nupdated body"

    activated = await activate_admin_legal_document(None, updated, store=store)
    loaded = await get_admin_legal_document(None, activated.id, store=store)
    documents = await list_admin_legal_documents(None, store=store)

    assert activated.is_active is True
    assert loaded is not None
    assert loaded.is_active is True
    assert any(item.id == created.id for item in documents)
