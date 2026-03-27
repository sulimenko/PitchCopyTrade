from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Iterable
from uuid import uuid4

from starlette.datastructures import UploadFile

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import (
    MessageChannel,
    MessageDeliver,
    MessageKind,
    MessageModeration,
    MessageStatus,
    MessageType,
    RiskLevel,
    StrategyStatus,
)
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.storage.base import StorageBackend
from pitchcopytrade.storage.local import LocalFilesystemStorage

MIN_REQUIRED_LEGS = 1
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
}


@dataclass(slots=True)
class AuthorWorkspaceStats:
    strategies_total: int
    messages_total: int
    draft_messages: int
    live_messages: int


@dataclass(slots=True)
class WatchlistCandidate:
    id: str
    ticker: str
    name: str
    board: str
    source: str = "catalog"


@dataclass(slots=True)
class StructuredLegFormData:
    instrument_id: str
    side: str
    entry_from: Decimal | None
    entry_to: Decimal | None
    stop_loss: Decimal | None
    take_profit_1: Decimal | None
    take_profit_2: Decimal | None
    take_profit_3: Decimal | None
    time_horizon: str | None
    note: str | None


@dataclass(slots=True)
class IncomingAttachment:
    filename: str
    content_type: str
    data: bytes


@dataclass(slots=True)
class RecommendationFormData:
    strategy_id: str
    kind: MessageKind
    status: MessageStatus
    title: str | None
    thread: str | None = None
    parent: str | None = None
    deliver: list[str] = field(default_factory=list)
    channel: list[str] = field(default_factory=list)
    moderation: MessageModeration = MessageModeration.REQUIRED
    message_type: MessageType = MessageType.MIXED
    text_body: str | None = None
    text_plain: str | None = None
    documents: list[dict[str, object]] = field(default_factory=list)
    deals: list[dict[str, object]] = field(default_factory=list)
    schedule: datetime | None = None
    published: datetime | None = None
    archived: datetime | None = None
    summary: str | None = None
    thesis: str | None = None
    market_context: str | None = None
    requires_moderation: bool = True
    scheduled_for: datetime | None = None
    legs: list[StructuredLegFormData] = field(default_factory=list)
    attachments: list[IncomingAttachment] = field(default_factory=list)
    message_mode: str = "mixed"
    message_text: str | None = None
    document_caption: str | None = None
    structured_instrument_id: str | None = None
    structured_side: str | None = None
    structured_price: Decimal | None = None
    structured_quantity: Decimal | None = None
    bundle_id: str | None = None


@dataclass(slots=True)
class AuthorStrategyFormData:
    slug: str
    title: str
    short_description: str
    risk_level: RiskLevel
    min_capital_rub: int | None


async def get_author_workspace_stats(repository: AuthorRepository, author: AuthorProfile) -> AuthorWorkspaceStats:
    strategies_total = await repository.count_author_strategies(author.id)
    messages_total = await repository.count_author_messages(author.id)
    draft_messages = 0
    live_messages = 0
    return AuthorWorkspaceStats(
        strategies_total=strategies_total,
        messages_total=messages_total,
        draft_messages=draft_messages,
        live_messages=live_messages,
    )


async def list_author_strategies(repository: AuthorRepository, author: AuthorProfile) -> list[Strategy]:
    return await repository.list_author_strategies(author.id)


async def get_author_strategy(
    repository: AuthorRepository,
    author: AuthorProfile,
    strategy_id: str,
) -> Strategy | None:
    return await repository.get_author_strategy(author.id, strategy_id)


async def create_author_strategy(
    repository: AuthorRepository,
    author: AuthorProfile,
    data: AuthorStrategyFormData,
) -> Strategy:
    strategy = Strategy(
        author_id=author.id,
        slug=data.slug,
        title=data.title,
        short_description=data.short_description,
        risk_level=data.risk_level,
        min_capital_rub=data.min_capital_rub,
        status=StrategyStatus.DRAFT,
        is_public=False,
    )
    repository.add(strategy)
    await repository.commit()
    await repository.refresh(strategy)
    return strategy


async def update_author_strategy(
    repository: AuthorRepository,
    strategy: Strategy,
    data: AuthorStrategyFormData,
) -> Strategy:
    if strategy.status is not StrategyStatus.DRAFT:
        raise ValueError("Редактировать можно только стратегии в статусе «Черновик».")
    strategy.slug = data.slug
    strategy.title = data.title
    strategy.short_description = data.short_description
    strategy.risk_level = data.risk_level
    strategy.min_capital_rub = data.min_capital_rub
    await repository.commit()
    await repository.refresh(strategy)
    return strategy


async def list_active_instruments(repository: AuthorRepository) -> list[Instrument]:
    return await repository.list_active_instruments()


async def list_author_watchlist(repository: AuthorRepository, author: AuthorProfile) -> list[Instrument]:
    await ensure_author_watchlist_seed(repository, author)
    return await repository.list_author_watchlist(author.id)


async def add_author_watchlist_instrument(
    repository: AuthorRepository,
    author: AuthorProfile,
    instrument_id: str,
) -> Instrument:
    instrument = await repository.add_author_watchlist_instrument(author.id, instrument_id)
    if instrument is None:
        raise ValueError("Инструмент не найден.")
    return instrument


async def remove_author_watchlist_instrument(
    repository: AuthorRepository,
    author: AuthorProfile,
    instrument_id: str,
) -> None:
    removed = await repository.remove_author_watchlist_instrument(author.id, instrument_id)
    if not removed:
        raise ValueError("Инструмент не найден в watchlist.")


async def ensure_author_watchlist_seed(repository: AuthorRepository, author: AuthorProfile) -> list[Instrument]:
    watchlist = await repository.list_author_watchlist(author.id)
    if watchlist:
        return watchlist
    instruments = await repository.list_active_instruments()
    for instrument in instruments[:12]:
        await repository.add_author_watchlist_instrument(author.id, instrument.id)
    return await repository.list_author_watchlist(author.id)


async def search_author_watchlist_candidates(
    repository: AuthorRepository,
    author: AuthorProfile,
    query: str,
) -> list[WatchlistCandidate]:
    normalized = query.strip().lower()
    if len(normalized) < 2:
        return []

    watchlist = await ensure_author_watchlist_seed(repository, author)
    watchlist_ids = {item.id for item in watchlist}
    instruments = await repository.list_active_instruments()
    local_candidates = [
        WatchlistCandidate(
            id=item.id,
            ticker=item.ticker,
            name=item.name,
            board=item.board,
        )
        for item in instruments
        if item.id not in watchlist_ids and _matches_instrument_query(item, normalized)
    ]

    if len(local_candidates) <= 2:
        external_candidates = await _search_external_instruments_stub(normalized, watchlist_ids | {item.id for item in instruments})
        local_candidates.extend(external_candidates)

    seen: set[str] = set()
    deduped: list[WatchlistCandidate] = []
    for item in sorted(local_candidates, key=lambda candidate: (candidate.source, candidate.ticker.lower(), candidate.name.lower())):
        if item.id in seen:
            continue
        seen.add(item.id)
        deduped.append(item)
    return deduped


async def list_author_recommendations(repository: AuthorRepository, author: AuthorProfile) -> list[Message]:
    return await repository.list_author_messages(author.id)


async def get_author_recommendation(
    repository: AuthorRepository,
    author: AuthorProfile,
    recommendation_id: str,
) -> Message | None:
    return await repository.get_author_message(author.id, recommendation_id)


async def create_author_recommendation(
    repository: AuthorRepository,
    author: AuthorProfile,
    data: RecommendationFormData,
    *,
    uploaded_by_user_id: str | None = None,
    storage: StorageBackend | None = None,
) -> Message:
    message = _build_message_entity(author, data, uploaded_by_user_id=uploaded_by_user_id)
    repository.add(message)
    await repository.flush()
    _finalize_root_thread(message)
    await repository.commit()
    await repository.refresh(message)
    return message


async def update_author_recommendation(
    repository: AuthorRepository,
    message: Message,
    data: RecommendationFormData,
    *,
    uploaded_by_user_id: str | None = None,
    storage: StorageBackend | None = None,
) -> Message:
    if message.status not in {MessageStatus.DRAFT.value, MessageStatus.REVIEW.value}:
        raise ValueError("Редактировать можно только сообщения в статусах «Черновик» и «На модерации».")
    updated = _build_message_entity(author=message.author or author, data=data, uploaded_by_user_id=uploaded_by_user_id, existing=message)
    message.strategy_id = updated.strategy_id
    message.bundle_id = updated.bundle_id
    message.author_id = updated.author_id
    message.user_id = updated.user_id
    message.moderator_id = updated.moderator_id
    message.kind = updated.kind
    message.type = updated.type
    message.status = updated.status
    message.moderation = updated.moderation
    message.title = updated.title
    message.comment = updated.comment
    message.schedule = updated.schedule
    message.published = updated.published
    message.archived = updated.archived
    message.documents = updated.documents
    message.text = updated.text
    message.deals = updated.deals
    message.deliver = updated.deliver
    message.channel = updated.channel
    message.thread = updated.thread
    message.parent = updated.parent
    await repository.commit()
    await repository.refresh(message)
    return message


async def remove_recommendation_attachments(
    repository: AuthorRepository,
    recommendation: Message,
    attachment_ids: Iterable[str],
    *,
    storage: StorageBackend | None = None,
) -> Message:
    runtime_storage = storage or LocalFilesystemStorage()
    targets = {item.strip() for item in attachment_ids if item and item.strip()}
    if not targets:
        return recommendation

    documents = [item for item in recommendation.documents if str(item.get("id")) not in targets]
    removed = [item for item in recommendation.documents if str(item.get("id")) in targets]
    for attachment in removed:
        object_key = attachment.get("object_key")
        if object_key:
            runtime_storage.delete_object(str(object_key))
    recommendation.documents = documents
    return recommendation


async def get_author_by_user(repository: AuthorRepository, user: User) -> AuthorProfile | None:
    return await repository.get_author_by_user_id(user.id)


def build_recommendation_form_data(
    *,
    strategy_id: str,
    bundle_id: str = "",
    kind_value: str,
    status_value: str,
    title: str,
    type_value: str | None = None,
    deliver: Iterable[str] | None = None,
    channel: Iterable[str] | None = None,
    message_mode: str = "mixed",
    message_text: str = "",
    document_caption: str = "",
    structured_instrument_id: str = "",
    structured_side_value: str = "",
    structured_price: str = "",
    structured_quantity: str = "",
    text_body: str = "",
    text_plain: str = "",
    documents: Iterable[dict[str, object]] | None = None,
    deals: Iterable[dict[str, object]] | None = None,
    summary: str = "",
    thesis: str = "",
    market_context: str = "",
    author_requires_moderation: bool,
    scheduled_for: str,
    allowed_strategy_ids: set[str],
    allowed_instrument_ids: set[str],
    leg_rows: Iterable[dict[str, str]],
    attachments: Iterable[IncomingAttachment],
) -> RecommendationFormData:
    normalized_strategy_id = strategy_id.strip()
    if not normalized_strategy_id or normalized_strategy_id not in allowed_strategy_ids:
        raise ValueError("Выберите стратегию автора.")

    try:
        kind = MessageKind(_normalize_message_kind_value(kind_value))
    except ValueError as exc:
        raise ValueError("Некорректный kind сообщения.") from exc

    try:
        status = MessageStatus(_normalize_message_status_value(status_value))
    except ValueError as exc:
        raise ValueError("Некорректный статус сообщения.") from exc

    scheduled_for_value = _parse_datetime_local(scheduled_for.strip()) if scheduled_for.strip() else None
    if status == MessageStatus.SCHEDULED and scheduled_for_value is None:
        raise ValueError("Для scheduled нужен schedule.")

    parsed_documents = list(documents or [])
    parsed_deals = list(deals or [])
    normalized_type = _normalize_message_type_value(type_value or message_mode or "")
    if normalized_type not in {item.value for item in MessageType}:
        raise ValueError("Некорректный type сообщения.")

    structured_side: str | None = None
    if structured_side_value.strip():
        structured_side = structured_side_value.strip()

    structured_price_value = _parse_decimal(structured_price.strip(), "Некорректная цена.") if structured_price.strip() else None
    structured_quantity_value = _parse_decimal(structured_quantity.strip(), "Некорректное количество.") if structured_quantity.strip() else None
    normalized_message_text = (text_body or message_text).strip() or None
    normalized_message_plain = text_plain.strip() or None
    normalized_document_caption = document_caption.strip() or None
    normalized_structured_instrument_id = structured_instrument_id.strip() or None
    parsed_attachments = list(attachments)
    parsed_legs = _build_leg_rows(
        leg_rows,
        allowed_instrument_ids,
        require_legs=False,
    )
    if not parsed_deals and parsed_legs:
        parsed_deals = [_deal_from_leg(leg) for leg in parsed_legs]

    if normalized_type == MessageType.TEXT.value:
        if normalized_message_text is None:
            raise ValueError("Для text message нужен текст сообщения.")
    elif normalized_type == MessageType.DOCUMENT.value:
        if not parsed_documents and not parsed_attachments:
            raise ValueError("Для document message нужен документ.")
    elif normalized_type == MessageType.DEAL.value:
        if not parsed_deals and not parsed_legs:
            raise ValueError("Для deal message нужна сделка.")
    else:
        if normalized_message_text is None and not parsed_documents and not parsed_deals:
            raise ValueError("Для mixed message нужен хотя бы один блок контента.")

    if status == MessageStatus.SCHEDULED and scheduled_for_value is None:
        raise ValueError("Для scheduled message нужен schedule.")

    deliver_items = [str(item).strip() for item in (deliver or [MessageDeliver.STRATEGY.value]) if str(item).strip()]
    channel_items = [str(item).strip() for item in (channel or [MessageChannel.TELEGRAM.value, MessageChannel.MINIAPP.value]) if str(item).strip()]
    if not deliver_items:
        deliver_items = [MessageDeliver.STRATEGY.value]
    if not channel_items:
        channel_items = [MessageChannel.TELEGRAM.value, MessageChannel.MINIAPP.value]

    if MessageDeliver.STRATEGY.value in deliver_items and not normalized_strategy_id:
        raise ValueError("Для deliver=strategy нужна strategy.")
    normalized_bundle_id = bundle_id.strip() or None
    if MessageDeliver.BUNDLE.value in deliver_items and normalized_bundle_id is None:
        raise ValueError("Для deliver=bundle нужна bundle.")

    return RecommendationFormData(
        strategy_id=normalized_strategy_id,
        kind=kind,
        status=status,
        title=title.strip() or None,
        deliver=deliver_items,
        channel=channel_items,
        moderation=MessageModeration.REQUIRED if author_requires_moderation else MessageModeration.DIRECT,
        message_type=MessageType(normalized_type),
        text_body=normalized_message_text,
        text_plain=normalized_message_plain,
        documents=parsed_documents,
        deals=parsed_deals,
        schedule=scheduled_for_value,
        published=None,
        archived=None,
        summary=summary.strip() or None,
        thesis=thesis.strip() or None,
        market_context=market_context.strip() or None,
        requires_moderation=author_requires_moderation,
        scheduled_for=scheduled_for_value,
        legs=parsed_legs,
        attachments=parsed_attachments,
        message_mode=normalized_type,
        message_text=normalized_message_text,
        document_caption=normalized_document_caption,
        structured_instrument_id=normalized_structured_instrument_id,
        structured_side=structured_side,
        structured_price=structured_price_value,
        structured_quantity=structured_quantity_value,
        bundle_id=normalized_bundle_id,
    )


def build_author_strategy_form_data(
    *,
    title: str,
    slug: str,
    short_description: str,
    risk_level_value: str,
    min_capital_rub: str,
    existing_strategies: list[Strategy],
    current_strategy_id: str | None = None,
) -> AuthorStrategyFormData:
    normalized_title = title.strip()
    if not normalized_title:
        raise ValueError("Название стратегии обязательно.")

    normalized_slug = _slugify(slug or normalized_title)
    if not normalized_slug:
        raise ValueError("Слаг стратегии обязателен.")

    if any(item.slug == normalized_slug and item.id != current_strategy_id for item in existing_strategies):
        raise ValueError("Стратегия с таким slug уже существует.")

    try:
        risk_level = RiskLevel(risk_level_value)
    except ValueError as exc:
        raise ValueError("Некорректный уровень риска.") from exc

    min_capital_value = int(min_capital_rub) if min_capital_rub.strip() else None

    return AuthorStrategyFormData(
        slug=normalized_slug,
        title=normalized_title,
        short_description=short_description.strip(),
        risk_level=risk_level,
        min_capital_rub=min_capital_value,
    )


async def normalize_attachment_uploads(files: Iterable[UploadFile]) -> list[IncomingAttachment]:
    uploads: list[IncomingAttachment] = []
    for item in files:
        filename = (item.filename or "").strip()
        if not filename:
            continue
        content_type = (item.content_type or "application/octet-stream").strip()
        if content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise ValueError("Разрешены только PDF и изображения JPG.")
        data = await item.read()
        if not data:
            raise ValueError("Нельзя загрузить пустой файл.")
        if len(data) > MAX_ATTACHMENT_SIZE_BYTES:
            raise ValueError("Файл слишком большой. Лимит 10 MB.")
        uploads.append(
            IncomingAttachment(
                filename=Path(filename).name,
                content_type=content_type,
                data=data,
            )
        )
    return uploads


def recommendation_form_values(message: Message | None) -> dict[str, object]:
    if message is None:
        return {
            "strategy_id": "",
            "bundle_id": "",
            "kind": MessageKind.IDEA.value,
            "status": MessageStatus.DRAFT.value,
            "title": "",
            "deliver": [MessageDeliver.STRATEGY.value],
            "channel": [MessageChannel.TELEGRAM.value, MessageChannel.MINIAPP.value],
            "message_type": MessageType.MIXED.value,
            "text_body": "",
            "text_plain": "",
            "documents": [],
            "deals": [],
            "thread": "",
            "parent": "",
            "moderation": MessageModeration.REQUIRED.value,
            "schedule": "",
            "published": "",
            "archived": "",
            "summary": "",
            "thesis": "",
            "market_context": "",
            "requires_moderation": False,
            "scheduled_for": "",
            "legs": [_blank_leg_value("0")],
            "message_mode": "mixed",
            "message_text": "",
            "document_caption": "",
            "structured_instrument_id": "",
            "structured_side": "",
            "structured_price": "",
            "structured_quantity": "",
        }

    schedule = ""
    if message.schedule is not None:
        schedule = message.schedule.strftime("%Y-%m-%dT%H:%M")

    legs: list[dict[str, str]] = []
    for index, deal in enumerate(message.deals):
        legs.append(
            {
                "row_id": str(index),
                "instrument_id": str(deal.get("instrument_id") or ""),
                "side": str(deal.get("side") or ""),
                "entry_from": str(deal.get("entry_from") or ""),
                "entry_to": str(deal.get("entry_to") or ""),
                "stop_loss": str(deal.get("stop_loss") or ""),
                "take_profit_1": str(deal.get("take_profit_1") or ""),
                "take_profit_2": str(deal.get("take_profit_2") or ""),
                "take_profit_3": str(deal.get("take_profit_3") or ""),
                "time_horizon": str(deal.get("time_horizon") or ""),
                "note": str(deal.get("note") or ""),
            }
        )

    if not legs:
        legs = [_blank_leg_value("0")]

    text_payload = message.text or {}

    return {
        "strategy_id": message.strategy_id or "",
        "bundle_id": message.bundle_id or "",
        "kind": message.kind or MessageKind.IDEA.value,
        "status": message.status or MessageStatus.DRAFT.value,
        "title": message.title or "",
        "deliver": list(message.deliver or []),
        "channel": list(message.channel or []),
        "message_type": message.type or MessageType.MIXED.value,
        "text_body": str(text_payload.get("body") or ""),
        "text_plain": str(text_payload.get("plain") or ""),
        "documents": list(message.documents or []),
        "deals": list(message.deals or []),
        "thread": message.thread or "",
        "parent": message.parent or "",
        "moderation": message.moderation or MessageModeration.REQUIRED.value,
        "schedule": schedule,
        "published": message.published.strftime("%Y-%m-%dT%H:%M") if message.published else "",
        "archived": message.archived.strftime("%Y-%m-%dT%H:%M") if message.archived else "",
        "summary": message.comment or "",
        "thesis": "",
        "market_context": "",
        "requires_moderation": message.moderation == MessageModeration.REQUIRED.value,
        "scheduled_for": schedule,
        "legs": legs,
        "message_mode": message.type or MessageType.MIXED.value,
        "message_text": str(text_payload.get("body") or ""),
        "document_caption": str(text_payload.get("title") or ""),
        "structured_instrument_id": str((message.deals[0] if message.deals else {}).get("instrument_id") or ""),
        "structured_side": str((message.deals[0] if message.deals else {}).get("side") or ""),
        "structured_price": str((message.deals[0] if message.deals else {}).get("entry_from") or ""),
        "structured_quantity": str((message.deals[0] if message.deals else {}).get("quantity") or ""),
    }


def build_leg_rows_from_form(form) -> list[dict[str, str]]:
    pattern = re.compile(r"^leg_(\d+)_(.+)$")
    indexes = {
        match.group(1)
        for key in form.keys()
        if (match := pattern.match(str(key)))
    }
    if not indexes:
        return [_blank_leg_value("0")]

    rows: list[dict[str, str]] = []
    for index in sorted(indexes, key=lambda item: int(item)):
        rows.append(
            {
                "row_id": str(index),
                "instrument_id": str(form.get(f"leg_{index}_instrument_id", "") or ""),
                "side": str(form.get(f"leg_{index}_side", "") or ""),
                "entry_from": str(form.get(f"leg_{index}_entry_from", "") or ""),
                "entry_to": str(form.get(f"leg_{index}_entry_to", "") or ""),
                "stop_loss": str(form.get(f"leg_{index}_stop_loss", "") or ""),
                "take_profit_1": str(form.get(f"leg_{index}_take_profit_1", "") or ""),
                "take_profit_2": str(form.get(f"leg_{index}_take_profit_2", "") or ""),
                "take_profit_3": str(form.get(f"leg_{index}_take_profit_3", "") or ""),
                "time_horizon": str(form.get(f"leg_{index}_time_horizon", "") or ""),
                "note": str(form.get(f"leg_{index}_note", "") or ""),
            }
        )
    return rows


def leg_form_values_from_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    if not rows:
        return [_blank_leg_value("0")]
    return [
        {
            "row_id": str(row.get("row_id", index)),
            "instrument_id": row.get("instrument_id", ""),
            "side": row.get("side", ""),
            "entry_from": row.get("entry_from", ""),
            "entry_to": row.get("entry_to", ""),
            "stop_loss": row.get("stop_loss", ""),
            "take_profit_1": row.get("take_profit_1", ""),
            "take_profit_2": row.get("take_profit_2", ""),
            "take_profit_3": row.get("take_profit_3", ""),
            "time_horizon": row.get("time_horizon", ""),
            "note": row.get("note", ""),
        }
        for index, row in enumerate(rows)
    ]


def build_attachment_object_key(message_id: str, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    return f"messages/{message_id}/{uuid4().hex}_{safe_name}"


def _finalize_root_thread(message: Message) -> None:
    if not message.thread:
        message.thread = message.id


def _apply_publish_state(message: Message) -> None:
    now = datetime.now(timezone.utc)
    if message.status == MessageStatus.SCHEDULED:
        message.published = None
    elif message.status == MessageStatus.PUBLISHED:
        message.schedule = None
        if message.published is None:
            message.published = now
    else:
        message.published = None
    if message.status == MessageStatus.ARCHIVED:
        message.archived = message.archived or now
    else:
        message.archived = None


def _build_leg_rows(
    rows: Iterable[dict[str, str]],
    allowed_instrument_ids: set[str],
    *,
    require_legs: bool = True,
) -> list[StructuredLegFormData]:
    legs: list[StructuredLegFormData] = []
    for index, row in enumerate(rows, start=1):
        if not any((value or "").strip() for key, value in row.items() if key != "row_id"):
            continue

        instrument_id = row.get("instrument_id", "").strip()
        if not instrument_id or instrument_id not in allowed_instrument_ids:
            raise ValueError(f"Leg {index}: выберите допустимый инструмент.")

        side_value = row.get("side", "").strip()
        if side_value not in {"buy", "sell"}:
            raise ValueError(f"Leg {index}: выберите направление сделки.")
        side = side_value

        entry_from = _parse_decimal(row.get("entry_from", ""), f"Leg {index}: некорректный entry_from.")
        entry_to = _parse_decimal(row.get("entry_to", ""), f"Leg {index}: некорректный entry_to.")
        stop_loss = _parse_decimal(row.get("stop_loss", ""), f"Leg {index}: некорректный stop_loss.")
        take_profit_1 = _parse_decimal(row.get("take_profit_1", ""), f"Leg {index}: некорректный take_profit_1.")
        take_profit_2 = _parse_decimal(row.get("take_profit_2", ""), f"Leg {index}: некорректный take_profit_2.")
        take_profit_3 = _parse_decimal(row.get("take_profit_3", ""), f"Leg {index}: некорректный take_profit_3.")

        if entry_from is not None and entry_to is not None and entry_to < entry_from:
            raise ValueError(f"Leg {index}: entry_to не может быть меньше entry_from.")

        legs.append(
            StructuredLegFormData(
                instrument_id=instrument_id,
                side=side,
                entry_from=entry_from,
                entry_to=entry_to,
                stop_loss=stop_loss,
                take_profit_1=take_profit_1,
                take_profit_2=take_profit_2,
                take_profit_3=take_profit_3,
                time_horizon=row.get("time_horizon", "").strip() or None,
                note=row.get("note", "").strip() or None,
            )
        )
    if require_legs and len(legs) < MIN_REQUIRED_LEGS:
        raise ValueError("Добавьте минимум одну бумагу с инструментом и направлением.")
    return legs


def _deal_from_leg(leg: StructuredLegFormData) -> dict[str, object]:
    return {
        "instrument_id": leg.instrument_id,
        "side": leg.side,
        "entry_from": _format_decimal(leg.entry_from),
        "entry_to": _format_decimal(leg.entry_to),
        "stop_loss": _format_decimal(leg.stop_loss),
        "take_profit_1": _format_decimal(leg.take_profit_1),
        "take_profit_2": _format_decimal(leg.take_profit_2),
        "take_profit_3": _format_decimal(leg.take_profit_3),
        "time_horizon": leg.time_horizon,
        "note": leg.note,
    }


def _sanitize_html(value: str | None) -> str:
    if not value:
        return ""
    sanitized = re.sub(r"<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", "", value, flags=re.I | re.S)
    sanitized = re.sub(r"\son[a-z]+\s*=\s*(['\"]).*?\1", "", sanitized, flags=re.I | re.S)
    sanitized = re.sub(r"javascript\s*:", "", sanitized, flags=re.I)
    return sanitized.strip()


def _html_to_plain(value: str) -> str:
    plain = re.sub(r"<[^>]+>", " ", value)
    plain = re.sub(r"\s+", " ", plain)
    return plain.strip()


def _normalize_message_kind_value(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "new_idea":
        return MessageKind.IDEA.value
    return normalized


def _normalize_message_status_value(value: str) -> str:
    normalized = value.strip().lower()
    if normalized in {"closed", "cancelled"}:
        return MessageStatus.ARCHIVED.value
    return normalized


def _normalize_message_type_value(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        return MessageType.MIXED.value
    if normalized == "structured":
        return MessageType.MIXED.value
    return normalized


def _normalize_message_moderation_value(value: object) -> str:
    normalized = str(getattr(value, "value", value)).strip().lower()
    if normalized == "true":
        return MessageModeration.REQUIRED.value
    if normalized == "false":
        return MessageModeration.DIRECT.value
    if normalized not in {item.value for item in MessageModeration}:
        return MessageModeration.REQUIRED.value
    return normalized


def _build_message_entity(
    author: AuthorProfile,
    data: RecommendationFormData,
    *,
    uploaded_by_user_id: str | None = None,
    existing: Message | None = None,
) -> Message:
    message = existing or Message()
    if not getattr(message, "id", None):
        message.id = str(uuid4())
    body = _sanitize_html(data.text_body or data.message_text or "")
    plain = data.text_plain or _html_to_plain(body)
    documents = list(data.documents)
    deals = list(data.deals)
    if not deals and data.legs:
        deals = [_deal_from_leg(item) for item in data.legs]
    if not body and data.message_type is MessageType.TEXT and plain:
        body = f"<p>{plain}</p>"
    if data.message_type is MessageType.DOCUMENT and data.document_caption and not body:
        body = f"<p>{_sanitize_html(data.document_caption)}</p>"

    message.author_id = author.id
    message.strategy_id = data.strategy_id
    message.bundle_id = data.bundle_id
    message.kind = MessageKind(_normalize_message_kind_value(getattr(data.kind, "value", str(data.kind))))
    message.type = MessageType(_normalize_message_type_value(getattr(data.message_type, "value", str(data.message_type))))
    message.status = MessageStatus(_normalize_message_status_value(getattr(data.status, "value", str(data.status))))
    message.moderation = MessageModeration(_normalize_message_moderation_value(data.moderation))
    message.title = data.title
    message.comment = data.document_caption or data.summary or data.thesis or data.market_context
    message.deliver = list(dict.fromkeys(data.deliver or [MessageDeliver.STRATEGY.value]))
    message.channel = list(dict.fromkeys(data.channel or [MessageChannel.TELEGRAM.value, MessageChannel.MINIAPP.value]))
    message.thread = data.thread or message.thread
    message.parent = data.parent or message.parent
    message.schedule = data.schedule or data.scheduled_for
    message.published = data.published
    message.archived = data.archived
    message.documents = documents
    message.deals = deals
    message.text = {
        "body": body,
        "plain": plain,
        "title": data.title,
    }
    if not message.thread:
        message.thread = message.id
    _validate_message_contract(message)
    _apply_publish_state(message)
    return message


def _validate_message_contract(message: Message) -> None:
    if message.strategy_id is None and MessageDeliver.STRATEGY.value in (message.deliver or []):
        raise ValueError("Для deliver=strategy нужна strategy.")
    if message.bundle_id is None and MessageDeliver.BUNDLE.value in (message.deliver or []):
        raise ValueError("Для deliver=bundle нужна bundle.")
    if not message.thread and message.parent is not None:
        raise ValueError("Для дочернего сообщения нужен thread.")
    if message.status == MessageStatus.SCHEDULED and message.schedule is None:
        raise ValueError("Для scheduled нужен schedule.")
    if message.status == MessageStatus.PUBLISHED and message.published is None:
        raise ValueError("Для published нужен published.")
    body = str((message.text or {}).get("body") or "").strip()
    documents = list(message.documents or [])
    deals = list(message.deals or [])
    if message.type == MessageType.TEXT and not body:
        raise ValueError("Для text message нужен текст сообщения.")
    if message.type == MessageType.DOCUMENT and not documents:
        raise ValueError("Для document message нужен документ.")
    if message.type == MessageType.DEAL and not deals:
        raise ValueError("Для deal message нужна сделка.")
    if message.type == MessageType.MIXED and not (body or documents or deals):
        raise ValueError("Для mixed message нужен хотя бы один блок контента.")
    if message.kind in {MessageKind.UPDATE, MessageKind.CLOSE, MessageKind.CANCEL} and not message.parent:
        raise ValueError("Для update/close/cancel нужно parent.")
    if message.thread is None:
        raise ValueError("thread обязателен для всех сообщений.")


async def _store_attachments(
    repository: AuthorRepository,
    message: Message,
    *,
    attachments: list[IncomingAttachment],
    uploaded_by_user_id: str | None,
    storage: StorageBackend,
) -> None:
    storage.bootstrap()
    documents = list(message.documents or [])
    for item in attachments:
        object_key = build_attachment_object_key(message.id, item.filename)
        stored = storage.upload_bytes(object_key, item.data, item.content_type)
        documents.append(
            {
                "id": str(uuid4()),
                "object_key": stored.object_key,
                "original_filename": item.filename,
                "content_type": stored.content_type,
                "size_bytes": stored.size_bytes,
                "uploaded_by": uploaded_by_user_id,
                "kind": "attachment",
            }
        )
    message.documents = documents
    await repository.flush()


def _parse_datetime_local(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ValueError("Некорректный формат даты. Используйте YYYY-MM-DDTHH:MM.") from exc


def _parse_decimal(value: str, error_message: str) -> Decimal | None:
    normalized = value.strip()
    if not normalized:
        return None
    try:
        return Decimal(normalized.replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(error_message) from exc


def _format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value, "f").rstrip("0").rstrip(".") or "0"


def _blank_leg_value(row_id: str | int) -> dict[str, str]:
    return {
        "row_id": str(row_id),
        "instrument_id": "",
        "side": "",
        "entry_from": "",
        "entry_to": "",
        "stop_loss": "",
        "take_profit_1": "",
        "take_profit_2": "",
        "take_profit_3": "",
        "time_horizon": "",
        "note": "",
    }


def _matches_instrument_query(instrument: Instrument, query: str) -> bool:
    haystack = " ".join(
        [
            instrument.ticker.lower(),
            instrument.name.lower(),
            instrument.board.lower(),
        ]
    )
    return query in haystack


async def _search_external_instruments_stub(query: str, excluded_ids: set[str]) -> list[WatchlistCandidate]:
    _ = query
    _ = excluded_ids
    return []


def _slugify(text: str) -> str:
    normalized = text.lower().strip()
    normalized = re.sub(r"[^\w\s-]", "", normalized)
    normalized = re.sub(r"[\s_-]+", "-", normalized)
    return normalized.strip("-")[:120]
