from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.audit import AuditEvent
from pitchcopytrade.db.models.commerce import Payment, Subscription
from pitchcopytrade.db.models.enums import PaymentProvider, PaymentStatus, SubscriptionStatus
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore

TBANK_SUCCESS_STATUSES = {"CONFIRMED"}
TBANK_FAILED_STATUS_MAP: dict[str, PaymentStatus] = {
    "AUTH_FAIL": PaymentStatus.FAILED,
    "REJECTED": PaymentStatus.FAILED,
    "DEADLINE_EXPIRED": PaymentStatus.EXPIRED,
    "CANCELED": PaymentStatus.CANCELLED,
    "CANCELLED": PaymentStatus.CANCELLED,
    "EXPIRED": PaymentStatus.EXPIRED,
}


@dataclass(slots=True)
class PaymentSyncStats:
    checked: int = 0
    paid: int = 0
    failed: int = 0
    pending: int = 0


async def sync_tbank_pending_payments(
    session: AsyncSession | None,
    *,
    client: TBankAcquiringClient,
    now: datetime | None = None,
    store: FileDataStore | None = None,
) -> PaymentSyncStats:
    timestamp = now or datetime.now(timezone.utc)
    if session is None:
        file_store = store or FileDataStore()
        graph = FileDatasetGraph.load(file_store)
        stats = await _sync_tbank_pending_payments_file(graph, file_store, client=client, now=timestamp)
        return stats

    query = (
        select(Payment)
        .options(
            selectinload(Payment.subscriptions),
            selectinload(Payment.user),
            selectinload(Payment.product),
        )
        .where(Payment.provider == PaymentProvider.TBANK, Payment.status == PaymentStatus.PENDING)
    )
    result = await session.execute(query)
    payments = list(result.scalars().all())
    stats = PaymentSyncStats()
    for payment in payments:
        stats.checked += 1
        provider_payment_id = _extract_provider_payment_id(payment)
        if not provider_payment_id:
            stats.pending += 1
            continue
        state = await client.get_state(payment_id=provider_payment_id)
        _merge_payment_state(payment, state, checked_at=timestamp)
        provider_status = str(state.get("Status") or "").upper()
        if provider_status in TBANK_SUCCESS_STATUSES:
            _mark_payment_paid(payment, timestamp)
            _add_sync_audit_event(
                session,
                payment=payment,
                provider_status=provider_status,
                local_status=payment.status,
            )
            stats.paid += 1
        elif provider_status in TBANK_FAILED_STATUS_MAP:
            payment.status = TBANK_FAILED_STATUS_MAP[provider_status]
            for subscription in payment.subscriptions:
                subscription.status = SubscriptionStatus.CANCELLED
            _add_sync_audit_event(
                session,
                payment=payment,
                provider_status=provider_status,
                local_status=payment.status,
            )
            stats.failed += 1
        else:
            stats.pending += 1

    if stats.checked:
        await session.commit()
    return stats


async def _sync_tbank_pending_payments_file(
    graph: FileDatasetGraph,
    store: FileDataStore,
    *,
    client: TBankAcquiringClient,
    now: datetime,
) -> PaymentSyncStats:
    stats = PaymentSyncStats()
    for payment in graph.payments.values():
        if payment.provider != PaymentProvider.TBANK or payment.status != PaymentStatus.PENDING:
            continue
        stats.checked += 1
        provider_payment_id = _extract_provider_payment_id(payment)
        if not provider_payment_id:
            stats.pending += 1
            continue
        state = await client.get_state(payment_id=provider_payment_id)
        _merge_payment_state(payment, state, checked_at=now)
        provider_status = str(state.get("Status") or "").upper()
        if provider_status in TBANK_SUCCESS_STATUSES:
            _mark_payment_paid(payment, now)
            graph.add(
                _build_sync_audit_event(
                    payment=payment,
                    provider_status=provider_status,
                    local_status=payment.status,
                )
            )
            stats.paid += 1
        elif provider_status in TBANK_FAILED_STATUS_MAP:
            payment.status = TBANK_FAILED_STATUS_MAP[provider_status]
            for subscription in payment.subscriptions:
                subscription.status = SubscriptionStatus.CANCELLED
            graph.add(
                _build_sync_audit_event(
                    payment=payment,
                    provider_status=provider_status,
                    local_status=payment.status,
                )
            )
            stats.failed += 1
        else:
            stats.pending += 1

    if stats.checked:
        graph.save(store)
    return stats


def _extract_provider_payment_id(payment: Payment) -> str | None:
    if payment.external_id:
        return payment.external_id
    payload = payment.provider_payload or {}
    provider_payment_id = payload.get("provider_payment_id")
    if provider_payment_id is None:
        return None
    return str(provider_payment_id)


def _merge_payment_state(payment: Payment, state: dict[str, object], *, checked_at: datetime) -> None:
    payload = dict(payment.provider_payload or {})
    history = list(payload.get("state_history", []))
    history.append(
        {
            "checked_at": checked_at.isoformat(),
            "status": state.get("Status"),
            "payment_id": state.get("PaymentId"),
        }
    )
    payload["last_state"] = state
    payload["state_history"] = history[-10:]
    payment.provider_payload = payload
    payment.updated_at = checked_at


def _mark_payment_paid(payment: Payment, timestamp: datetime) -> None:
    payment.status = PaymentStatus.PAID
    payment.confirmed_at = payment.confirmed_at or timestamp
    for subscription in payment.subscriptions:
        subscription.status = SubscriptionStatus.TRIAL if subscription.is_trial else SubscriptionStatus.ACTIVE


def _build_sync_audit_event(
    *,
    payment: Payment,
    provider_status: str,
    local_status: PaymentStatus,
) -> AuditEvent:
    return AuditEvent(
        actor_user_id=None,
        entity_type="payment",
        entity_id=payment.id,
        action="worker.payment_state_sync",
        payload={
            "provider": payment.provider.value,
            "provider_status": provider_status,
            "payment_status": local_status.value,
        },
    )


def _add_sync_audit_event(
    session: AsyncSession,
    *,
    payment: Payment,
    provider_status: str,
    local_status: PaymentStatus,
) -> None:
    session.add(
        _build_sync_audit_event(
            payment=payment,
            provider_status=provider_status,
            local_status=local_status,
        )
    )
