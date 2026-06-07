from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.commerce import LegalDocument
from pitchcopytrade.db.models.enums import LegalDocumentType
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.compliance import activate_legal_document, create_legal_document_draft
from pitchcopytrade.services.legal_documents import build_legal_document_source_path
from pitchcopytrade.storage.local import LocalFilesystemStorage


@dataclass(slots=True)
class LegalDocumentFormData:
    document_type: LegalDocumentType
    version: str
    title: str
    content_md: str


def _file_legal_graph(store: FileDataStore | None = None) -> tuple[FileDatasetGraph, FileDataStore]:
    runtime_store = store or FileDataStore()
    graph = FileDatasetGraph.load(runtime_store)
    return graph, runtime_store


async def list_admin_legal_documents(
    session: AsyncSession | None,
    *,
    store: FileDataStore | None = None,
) -> list[LegalDocument]:
    if session is None:
        graph, _store = _file_legal_graph(store)
        items = list(graph.legal_documents.values())
        items.sort(key=lambda item: (item.document_type.value, item.version), reverse=True)
        return items
    query = (
        select(LegalDocument)
        .options(selectinload(LegalDocument.consents))
        .order_by(LegalDocument.document_type.asc(), LegalDocument.version.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_admin_legal_document(
    session: AsyncSession | None,
    document_id: str,
    *,
    store: FileDataStore | None = None,
) -> LegalDocument | None:
    if session is None:
        graph, _store = _file_legal_graph(store)
        return graph.legal_documents.get(document_id)
    query = select(LegalDocument).options(selectinload(LegalDocument.consents)).where(LegalDocument.id == document_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_admin_legal_document(
    session: AsyncSession | None,
    data: LegalDocumentFormData,
    *,
    storage: LocalFilesystemStorage | None = None,
    store: FileDataStore | None = None,
) -> LegalDocument:
    source_path = build_legal_document_source_path(
        LegalDocument(document_type=data.document_type, version=data.version, title=data.title, content_md=data.content_md)
    )
    document = create_legal_document_draft(
        document_type=data.document_type,
        version=data.version,
        title=data.title,
        content_md=data.content_md,
        source_path=source_path,
    )

    if session is None:
        graph, runtime_store = _file_legal_graph(store)
        _ensure_legal_version_is_unique(graph.legal_documents.values(), document)
        graph.add(document)
        _write_legal_markdown(document, data.content_md, storage=storage)
        graph.save(runtime_store)
        return graph.legal_documents[document.id]

    existing = await _find_same_type_version(session, data.document_type, data.version)
    if existing is not None:
        raise ValueError("Версия документа уже существует")
    session.add(document)
    _write_legal_markdown(document, data.content_md, storage=storage)
    await session.commit()
    await session.refresh(document)
    return document


async def update_admin_legal_document(
    session: AsyncSession | None,
    document: LegalDocument,
    data: LegalDocumentFormData,
    *,
    storage: LocalFilesystemStorage | None = None,
    store: FileDataStore | None = None,
) -> LegalDocument:
    if document.is_active:
        raise ValueError("Активную версию документа нельзя редактировать. Создайте новую версию.")
    document.document_type = data.document_type
    document.version = data.version
    document.title = data.title
    document.content_md = data.content_md
    document.source_path = build_legal_document_source_path(document)

    if session is None:
        graph, runtime_store = _file_legal_graph(store)
        persisted = graph.legal_documents.get(document.id)
        if persisted is None:
            raise ValueError("Legal document not found")
        _ensure_legal_version_is_unique(
            [item for item in graph.legal_documents.values() if item.id != document.id],
            document,
        )
        persisted.document_type = document.document_type
        persisted.version = document.version
        persisted.title = document.title
        persisted.content_md = document.content_md
        persisted.source_path = document.source_path
        _write_legal_markdown(persisted, data.content_md, storage=storage)
        graph.save(runtime_store)
        return persisted

    existing = await _find_same_type_version(session, data.document_type, data.version)
    if existing is not None and existing.id != document.id:
        raise ValueError("Версия документа уже существует")
    _write_legal_markdown(document, data.content_md, storage=storage)
    await session.commit()
    await session.refresh(document)
    return document


async def activate_admin_legal_document(
    session: AsyncSession | None,
    document: LegalDocument,
    *,
    store: FileDataStore | None = None,
) -> LegalDocument:
    if session is None:
        graph, runtime_store = _file_legal_graph(store)
        persisted = graph.legal_documents.get(document.id)
        if persisted is None:
            raise ValueError("Legal document not found")
        siblings = [item for item in graph.legal_documents.values() if item.document_type == persisted.document_type]
        activate_legal_document(persisted, siblings)
        graph.save(runtime_store)
        return persisted

    query = select(LegalDocument).where(LegalDocument.document_type == document.document_type)
    result = await session.execute(query)
    siblings = list(result.scalars().all())
    activate_legal_document(document, siblings)
    await session.commit()
    await session.refresh(document)
    return document


def _ensure_legal_version_is_unique(documents, target: LegalDocument) -> None:
    for item in documents:
        if item.document_type == target.document_type and item.version == target.version:
            raise ValueError("Версия документа уже существует")


def _write_legal_markdown(
    document: LegalDocument,
    content_md: str,
    *,
    storage: LocalFilesystemStorage | None = None,
) -> None:
    object_key = document.source_path or build_legal_document_source_path(document)
    runtime_storage = storage or LocalFilesystemStorage()
    runtime_storage.upload_bytes(
        object_key=object_key,
        data=content_md.encode("utf-8"),
        content_type="text/markdown",
    )


async def _find_same_type_version(
    session: AsyncSession,
    document_type: LegalDocumentType,
    version: str,
) -> LegalDocument | None:
    query = select(LegalDocument).where(
        LegalDocument.document_type == document_type,
        LegalDocument.version == version,
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()
