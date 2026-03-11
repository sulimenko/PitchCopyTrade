from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.commerce import LegalDocument, Payment, UserConsent
from pitchcopytrade.db.models.enums import LegalDocumentType


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ComplianceError(ValueError):
    pass


@dataclass(frozen=True)
class MissingConsent:
    document_type: LegalDocumentType
    version: str


def create_legal_document_draft(
    *,
    document_type: LegalDocumentType,
    version: str,
    title: str,
    content_md: str,
) -> LegalDocument:
    return LegalDocument(
        document_type=document_type,
        version=version,
        title=title,
        content_md=content_md,
        is_active=False,
        published_at=None,
    )


def activate_legal_document(
    target_document: LegalDocument,
    documents_of_same_type: list[LegalDocument],
    *,
    activated_at: datetime | None = None,
) -> LegalDocument:
    timestamp = activated_at or utcnow()
    for document in documents_of_same_type:
        if document.document_type == target_document.document_type:
            document.is_active = False

    target_document.is_active = True
    target_document.published_at = timestamp
    return target_document


def get_active_documents(documents: list[LegalDocument]) -> dict[LegalDocumentType, LegalDocument]:
    active: dict[LegalDocumentType, LegalDocument] = {}
    for document in documents:
        if document.is_active:
            active[document.document_type] = document
    return active


def record_user_consent(
    *,
    user: User,
    document: LegalDocument,
    source: str,
    payment: Payment | None = None,
    accepted_at: datetime | None = None,
    ip_address: str | None = None,
) -> UserConsent:
    if not document.is_active:
        raise ComplianceError("Consent can only be recorded for active legal documents")

    consent = UserConsent(
        user=user,
        document=document,
        payment=payment,
        accepted_at=accepted_at or utcnow(),
        source=source,
        ip_address=ip_address,
    )
    user.consents.append(consent)
    document.consents.append(consent)
    if payment is not None:
        payment.consents.append(consent)
    return consent


def ensure_required_consents_before_payment(
    *,
    user: User,
    required_documents: list[LegalDocument],
) -> None:
    missing: list[MissingConsent] = []
    consented_document_ids = {consent.document_id or getattr(consent.document, "id", None) for consent in user.consents}

    for document in required_documents:
        if not document.is_active:
            raise ComplianceError(f"Required document {document.document_type.value}:{document.version} is not active")
        if document.id not in consented_document_ids:
            missing.append(MissingConsent(document.document_type, document.version))

    if missing:
        details = ", ".join(f"{item.document_type.value}:{item.version}" for item in missing)
        raise ComplianceError(f"Missing required consents before payment: {details}")


def bind_consents_to_payment(*, consents: list[UserConsent], payment: Payment) -> None:
    for consent in consents:
        consent.payment = payment
        consent.payment_id = payment.id
        if consent not in payment.consents:
            payment.consents.append(consent)
