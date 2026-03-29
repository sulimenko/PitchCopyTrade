from __future__ import annotations

from datetime import datetime, timezone

import pytest

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.commerce import LegalDocument, Payment
from pitchcopytrade.db.models.enums import LegalDocumentType, PaymentProvider, PaymentStatus
from pitchcopytrade.services.compliance import (
    ComplianceError,
    activate_legal_document,
    bind_consents_to_payment,
    create_legal_document_draft,
    ensure_required_consents_before_payment,
    get_active_documents,
    record_user_consent,
)


def _make_active_document(document_type: LegalDocumentType, version: str) -> LegalDocument:
    document = LegalDocument(
        id=f"doc-{document_type.value}-{version}",
        document_type=document_type,
        version=version,
        title=f"{document_type.value} {version}",
        content_md="draft",
        is_active=True,
    )
    document.consents = []
    return document


def _make_user() -> User:
    user = User(id="user-1", username="alex")
    user.consents = []
    return user


def _make_payment() -> Payment:
    payment = Payment(
        id="payment-1",
        user_id="user-1",
        product_id="product-1",
        provider=PaymentProvider.STUB_MANUAL,
        status=PaymentStatus.CREATED,
        amount_rub=1000,
        discount_rub=0,
        final_amount_rub=1000,
        currency="RUB",
    )
    payment.consents = []
    return payment


def test_create_legal_document_draft_creates_inactive_document() -> None:
    draft = create_legal_document_draft(
        document_type=LegalDocumentType.OFFER,
        version="v1",
        title="Оферта",
        content_md="text",
    )

    assert draft.is_active is False
    assert draft.published_at is None


def test_activate_legal_document_switches_active_version() -> None:
    old = _make_active_document(LegalDocumentType.OFFER, "v1")
    new = create_legal_document_draft(
        document_type=LegalDocumentType.OFFER,
        version="v2",
        title="Оферта 2",
        content_md="text",
    )
    activated_at = datetime(2026, 3, 11, tzinfo=timezone.utc)

    activate_legal_document(new, [old, new], activated_at=activated_at)

    assert old.is_active is False
    assert new.is_active is True
    assert new.published_at == activated_at


def test_get_active_documents_returns_only_active_versions() -> None:
    offer = _make_active_document(LegalDocumentType.OFFER, "v2")
    privacy = _make_active_document(LegalDocumentType.PRIVACY_POLICY, "v1")
    inactive = create_legal_document_draft(
        document_type=LegalDocumentType.DISCLAIMER,
        version="v1",
        title="Дисклеймер",
        content_md="text",
    )

    active = get_active_documents([offer, privacy, inactive])

    assert active[LegalDocumentType.OFFER] is offer
    assert active[LegalDocumentType.PRIVACY_POLICY] is privacy
    assert LegalDocumentType.DISCLAIMER not in active


def test_record_user_consent_and_bind_to_payment() -> None:
    user = _make_user()
    payment = _make_payment()
    document = _make_active_document(LegalDocumentType.PAYMENT_CONSENT, "v1")

    consent = record_user_consent(
        user=user,
        document=document,
        payment=None,
        source="checkout",
        ip_address="127.0.0.1",
    )
    bind_consents_to_payment(consents=[consent], payment=payment)

    assert consent.user_id == user.id
    assert consent.document_id == document.id
    assert consent.payment_id == payment.id
    assert user.consents == []
    assert document.consents == []
    assert payment.consents == []


def test_ensure_required_consents_before_payment_fails_when_missing() -> None:
    user = _make_user()
    required_documents = [
        _make_active_document(LegalDocumentType.OFFER, "v2"),
        _make_active_document(LegalDocumentType.PRIVACY_POLICY, "v1"),
    ]

    with pytest.raises(ComplianceError, match="Missing required consents before payment"):
        ensure_required_consents_before_payment(user=user, required_documents=required_documents)


def test_ensure_required_consents_before_payment_accepts_matching_consents() -> None:
    user = _make_user()
    offer = _make_active_document(LegalDocumentType.OFFER, "v2")
    privacy = _make_active_document(LegalDocumentType.PRIVACY_POLICY, "v1")

    offer_consent = record_user_consent(user=user, document=offer, source="checkout")
    privacy_consent = record_user_consent(user=user, document=privacy, source="checkout")
    user.consents = [offer_consent, privacy_consent]

    ensure_required_consents_before_payment(user=user, required_documents=[offer, privacy])


def test_record_user_consent_rejects_inactive_document() -> None:
    user = _make_user()
    inactive = create_legal_document_draft(
        document_type=LegalDocumentType.OFFER,
        version="v3",
        title="Оферта 3",
        content_md="text",
    )
    inactive.consents = []

    with pytest.raises(ComplianceError, match="active legal documents"):
        record_user_consent(user=user, document=inactive, source="checkout")
