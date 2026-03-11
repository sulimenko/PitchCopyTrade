from __future__ import annotations

from pathlib import PurePosixPath

from pitchcopytrade.db.models.commerce import LegalDocument
from pitchcopytrade.storage.local import LocalFilesystemStorage


def build_legal_document_source_path(document: LegalDocument) -> str:
    return PurePosixPath("legal", document.document_type.value, f"{document.version}.md").as_posix()


def read_legal_document_markdown(document: LegalDocument) -> str:
    source_path = document.source_path or build_legal_document_source_path(document)
    storage = LocalFilesystemStorage()
    try:
        payload = storage.download_bytes(source_path)
    except FileNotFoundError:
        return document.content_md
    return payload.decode("utf-8")
