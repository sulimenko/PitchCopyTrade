from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
from typing import Iterable
from uuid import uuid4

from starlette.datastructures import UploadFile

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg, RecommendationMessage
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, RiskLevel, StrategyStatus, TradeSide
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
    recommendations_total: int
    draft_recommendations: int
    live_recommendations: int


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
    side: TradeSide
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
    kind: RecommendationKind
    status: RecommendationStatus
    title: str | None
    summary: str | None
    thesis: str | None
    market_context: str | None
    requires_moderation: bool
    scheduled_for: datetime | None
    legs: list[StructuredLegFormData]
    attachments: list[IncomingAttachment]
    message_mode: str = "structured"
    message_text: str | None = None
    document_caption: str | None = None
    structured_instrument_id: str | None = None
    structured_side: TradeSide | None = None
    structured_price: Decimal | None = None
    structured_quantity: Decimal | None = None


@dataclass(slots=True)
class AuthorStrategyFormData:
    slug: str
    title: str
    short_description: str
    risk_level: RiskLevel
    min_capital_rub: int | None


async def get_author_workspace_stats(repository: AuthorRepository, author: AuthorProfile) -> AuthorWorkspaceStats:
    strategies_total = await repository.count_author_strategies(author.id)
    recommendations_total = await repository.count_author_recommendations(author.id)
    draft_recommendations = await repository.count_author_recommendations(
        author.id,
        statuses=[RecommendationStatus.DRAFT],
    )
    live_recommendations = await repository.count_author_recommendations(
        author.id,
        statuses=[
            RecommendationStatus.PUBLISHED,
            RecommendationStatus.SCHEDULED,
            RecommendationStatus.APPROVED,
        ],
    )
    return AuthorWorkspaceStats(
        strategies_total=strategies_total,
        recommendations_total=recommendations_total,
        draft_recommendations=draft_recommendations,
        live_recommendations=live_recommendations,
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


async def list_author_recommendations(repository: AuthorRepository, author: AuthorProfile) -> list[Recommendation]:
    return await repository.list_author_recommendations(author.id)


async def get_author_recommendation(
    repository: AuthorRepository,
    author: AuthorProfile,
    recommendation_id: str,
) -> Recommendation | None:
    return await repository.get_author_recommendation(author.id, recommendation_id)


async def create_author_recommendation(
    repository: AuthorRepository,
    author: AuthorProfile,
    data: RecommendationFormData,
    *,
    uploaded_by_user_id: str | None = None,
    storage: StorageBackend | None = None,
) -> Recommendation:
    payload = _build_recommendation_payload(data)
    recommendation = Recommendation(
        author_id=author.id,
        strategy_id=data.strategy_id,
        kind=data.kind,
        status=data.status,
        title=data.title,
        summary=data.summary,
        thesis=data.thesis,
        market_context=data.market_context,
        recommendation_payload=payload,
        requires_moderation=data.requires_moderation,
        scheduled_for=data.scheduled_for,
    )
    _apply_publish_state(recommendation)
    _attach_legs(recommendation, data.legs)
    _attach_message(recommendation, data, payload, created_by_user_id=uploaded_by_user_id)
    repository.add(recommendation)
    await repository.flush()
    if data.attachments:
        await _store_attachments(
            repository,
            recommendation,
            attachments=data.attachments,
            uploaded_by_user_id=uploaded_by_user_id,
            storage=storage or LocalFilesystemStorage(),
        )
    await repository.commit()
    await repository.refresh(recommendation)
    return recommendation


async def update_author_recommendation(
    repository: AuthorRepository,
    recommendation: Recommendation,
    data: RecommendationFormData,
    *,
    uploaded_by_user_id: str | None = None,
    storage: StorageBackend | None = None,
) -> Recommendation:
    if recommendation.status not in {RecommendationStatus.DRAFT, RecommendationStatus.REVIEW}:
        raise ValueError("Редактировать можно только рекомендации в статусах «Черновик» и «На модерации».")
    payload = _build_recommendation_payload(data)
    recommendation.strategy_id = data.strategy_id
    recommendation.kind = data.kind
    recommendation.status = data.status
    recommendation.title = data.title
    recommendation.summary = data.summary
    recommendation.thesis = data.thesis
    recommendation.market_context = data.market_context
    recommendation.recommendation_payload = payload
    recommendation.requires_moderation = data.requires_moderation
    recommendation.scheduled_for = data.scheduled_for
    _apply_publish_state(recommendation)
    await _replace_legs(repository, recommendation, data.legs)
    recommendation.messages.append(_build_message(data, payload, created_by_user_id=uploaded_by_user_id))
    if data.attachments:
        await _store_attachments(
            repository,
            recommendation,
            attachments=data.attachments,
            uploaded_by_user_id=uploaded_by_user_id,
            storage=storage or LocalFilesystemStorage(),
        )
    await repository.commit()
    await repository.refresh(recommendation)
    return recommendation


async def remove_recommendation_attachments(
    repository: AuthorRepository,
    recommendation: Recommendation,
    attachment_ids: Iterable[str],
    *,
    storage: StorageBackend | None = None,
) -> Recommendation:
    runtime_storage = storage or LocalFilesystemStorage()
    targets = {item.strip() for item in attachment_ids if item and item.strip()}
    if not targets:
        return recommendation

    remaining: list[RecommendationAttachment] = []
    for attachment in list(recommendation.attachments):
        if attachment.id not in targets:
            remaining.append(attachment)
            continue
        runtime_storage.delete_object(attachment.object_key)
        await repository.delete(attachment)
    recommendation.attachments = remaining
    return recommendation


async def get_author_by_user(repository: AuthorRepository, user: User) -> AuthorProfile | None:
    return await repository.get_author_by_user_id(user.id)


def build_recommendation_form_data(
    *,
    strategy_id: str,
    kind_value: str,
    status_value: str,
    title: str,
    message_mode: str = "structured",
    message_text: str = "",
    document_caption: str = "",
    structured_instrument_id: str = "",
    structured_side_value: str = "",
    structured_price: str = "",
    structured_quantity: str = "",
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
        kind = RecommendationKind(kind_value)
    except ValueError as exc:
        raise ValueError("Некорректный тип публикации.") from exc

    try:
        status = RecommendationStatus(status_value)
    except ValueError as exc:
        raise ValueError("Некорректный статус рекомендации.") from exc

    scheduled_for_value = _parse_datetime_local(scheduled_for.strip()) if scheduled_for.strip() else None
    if status == RecommendationStatus.SCHEDULED and scheduled_for_value is None:
        raise ValueError("Для scheduled нужен planned datetime.")

    parsed_attachments = list(attachments)
    normalized_mode = (message_mode.strip() or "structured").lower()
    if normalized_mode not in {"text", "document", "structured"}:
        raise ValueError("Некорректный режим сообщения.")

    structured_side: TradeSide | None = None
    if structured_side_value.strip():
        try:
            structured_side = TradeSide(structured_side_value.strip())
        except ValueError as exc:
            raise ValueError("Некорректное направление structured-сообщения.") from exc

    structured_price_value = _parse_decimal(structured_price.strip(), "Некорректная цена.") if structured_price.strip() else None
    structured_quantity_value = _parse_decimal(structured_quantity.strip(), "Некорректное количество.") if structured_quantity.strip() else None
    normalized_message_text = message_text.strip() or None
    normalized_document_caption = document_caption.strip() or None
    normalized_structured_instrument_id = structured_instrument_id.strip() or None

    parsed_legs = _build_leg_rows(
        leg_rows,
        allowed_instrument_ids,
        require_legs=normalized_mode == "structured" and any(
            (value or "").strip()
            for row in leg_rows
            for key, value in row.items()
            if key != "row_id"
        ),
    )

    if normalized_mode == "structured" and not normalized_structured_instrument_id and parsed_legs:
        first_leg = parsed_legs[0]
        normalized_structured_instrument_id = first_leg.instrument_id
        if structured_side is None:
            structured_side = first_leg.side
        if structured_price_value is None:
            structured_price_value = first_leg.entry_from or first_leg.entry_to or Decimal("1")
        if structured_quantity_value is None:
            structured_quantity_value = Decimal("1")

    if normalized_mode == "text":
        if normalized_message_text is None:
            raise ValueError("Для text message нужен текст сообщения.")
    elif normalized_mode == "document":
        if not parsed_attachments:
            raise ValueError("Для document message нужен PDF или JPG.")
    else:
        if normalized_structured_instrument_id is None:
            raise ValueError("Для structured message нужен инструмент.")
        if structured_side is None:
            raise ValueError("Для structured message нужно выбрать Buy или Sell.")
        if structured_price_value is None:
            raise ValueError("Для structured message нужна цена.")
        if structured_quantity_value is None:
            raise ValueError("Для structured message нужно количество.")

    return RecommendationFormData(
        strategy_id=normalized_strategy_id,
        kind=kind,
        status=status,
        title=title.strip() or None,
        summary=summary.strip() or None,
        thesis=thesis.strip() or None,
        market_context=market_context.strip() or None,
        requires_moderation=author_requires_moderation,
        scheduled_for=scheduled_for_value,
        legs=parsed_legs,
        attachments=parsed_attachments,
        message_mode=normalized_mode,
        message_text=normalized_message_text,
        document_caption=normalized_document_caption,
        structured_instrument_id=normalized_structured_instrument_id,
        structured_side=structured_side,
        structured_price=structured_price_value,
        structured_quantity=structured_quantity_value,
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


def recommendation_form_values(recommendation: Recommendation | None) -> dict[str, object]:
    if recommendation is None:
        return {
            "strategy_id": "",
            "kind": RecommendationKind.NEW_IDEA.value,
            "status": RecommendationStatus.DRAFT.value,
            "title": "",
            "summary": "",
            "thesis": "",
            "market_context": "",
            "requires_moderation": False,
            "scheduled_for": "",
            "legs": [_blank_leg_value("0")],
            "message_mode": "structured",
            "message_text": "",
            "document_caption": "",
            "structured_instrument_id": "",
            "structured_side": "",
            "structured_price": "",
            "structured_quantity": "",
        }

    scheduled_for = ""
    if recommendation.scheduled_for is not None:
        scheduled_for = recommendation.scheduled_for.strftime("%Y-%m-%dT%H:%M")

    legs: list[dict[str, str]] = []
    for index, leg in enumerate(recommendation.legs):
        legs.append(
            {
                "row_id": str(index),
                "instrument_id": leg.instrument_id or "",
                "side": leg.side.value if leg.side else "",
                "entry_from": _format_decimal(leg.entry_from),
                "entry_to": _format_decimal(leg.entry_to),
                "stop_loss": _format_decimal(leg.stop_loss),
                "take_profit_1": _format_decimal(leg.take_profit_1),
                "take_profit_2": _format_decimal(leg.take_profit_2),
                "take_profit_3": _format_decimal(leg.take_profit_3),
                "time_horizon": leg.time_horizon or "",
                "note": leg.note or "",
            }
        )

    if not legs:
        legs = [_blank_leg_value("0")]

    return {
        "strategy_id": recommendation.strategy_id,
        "kind": recommendation.kind.value,
        "status": recommendation.status.value,
        "title": recommendation.title or "",
        "summary": recommendation.summary or "",
        "thesis": recommendation.thesis or "",
        "market_context": recommendation.market_context or "",
        "requires_moderation": recommendation.requires_moderation,
        "scheduled_for": scheduled_for,
        "legs": legs,
        "message_mode": (recommendation.recommendation_payload or {}).get("mode", "structured"),
        "message_text": (recommendation.recommendation_payload or {}).get("text", ""),
        "document_caption": (recommendation.recommendation_payload or {}).get("document_caption", ""),
        "structured_instrument_id": (recommendation.recommendation_payload or {}).get("instrument_id", ""),
        "structured_side": (recommendation.recommendation_payload or {}).get("side", ""),
        "structured_price": (recommendation.recommendation_payload or {}).get("price", ""),
        "structured_quantity": (recommendation.recommendation_payload or {}).get("quantity", ""),
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


def build_attachment_object_key(recommendation_id: str, filename: str) -> str:
    safe_name = Path(filename).name.replace(" ", "_")
    return f"recommendations/{recommendation_id}/{uuid4().hex}_{safe_name}"


def _apply_publish_state(recommendation: Recommendation) -> None:
    now = datetime.now(timezone.utc)

    if recommendation.status == RecommendationStatus.SCHEDULED:
        recommendation.published_at = None
    elif recommendation.status == RecommendationStatus.PUBLISHED:
        recommendation.scheduled_for = None
        if recommendation.published_at is None:
            recommendation.published_at = now
    else:
        recommendation.published_at = None

    recommendation.closed_at = now if recommendation.status == RecommendationStatus.CLOSED else None
    recommendation.cancelled_at = now if recommendation.status == RecommendationStatus.CANCELLED else None


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
        try:
            side = TradeSide(side_value)
        except ValueError as exc:
            raise ValueError(f"Leg {index}: выберите направление сделки.") from exc

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


async def _replace_legs(
    repository: AuthorRepository,
    recommendation: Recommendation,
    legs: list[StructuredLegFormData],
) -> None:
    existing_legs = list(recommendation.legs)
    for item in existing_legs:
        await repository.delete(item)
    recommendation.legs = []
    await repository.flush()
    _attach_legs(recommendation, legs)


def _attach_legs(recommendation: Recommendation, legs: list[StructuredLegFormData]) -> None:
    recommendation.legs = [
        RecommendationLeg(
            instrument_id=item.instrument_id,
            side=item.side,
            entry_from=item.entry_from,
            entry_to=item.entry_to,
            stop_loss=item.stop_loss,
            take_profit_1=item.take_profit_1,
            take_profit_2=item.take_profit_2,
            take_profit_3=item.take_profit_3,
            time_horizon=item.time_horizon,
            note=item.note,
        )
        for item in legs
    ]


def _build_recommendation_payload(data: RecommendationFormData) -> dict[str, object]:
    if data.message_mode == "text":
        return {
            "mode": "text",
            "text": data.message_text or "",
            "title": data.title or "",
        }
    if data.message_mode == "document":
        return {
            "mode": "document",
            "document_caption": data.document_caption or data.message_text or "",
            "attachments": [attachment.filename for attachment in data.attachments],
            "title": data.title or "",
        }
    amount = None
    if data.structured_price is not None and data.structured_quantity is not None:
        amount = data.structured_price * data.structured_quantity
    return {
        "mode": "structured",
        "instrument_id": data.structured_instrument_id,
        "side": data.structured_side.value if data.structured_side else None,
        "price": _format_decimal(data.structured_price) if data.structured_price is not None else None,
        "quantity": _format_decimal(data.structured_quantity) if data.structured_quantity is not None else None,
        "amount": _format_decimal(amount) if amount is not None else None,
        "title": data.title or "",
        "summary": data.summary or "",
    }


def _build_message(
    data: RecommendationFormData,
    payload: dict[str, object],
    *,
    created_by_user_id: str | None = None,
) -> RecommendationMessage:
    body = data.message_text
    if data.message_mode == "document":
        body = data.document_caption or data.message_text or "Документ"
    elif data.message_mode == "structured":
        body = _build_structured_message_body(data)
    return RecommendationMessage(
        created_by_user_id=created_by_user_id,
        mode=data.message_mode,
        body=body,
        payload=payload,
    )


def _build_structured_message_body(data: RecommendationFormData) -> str:
    parts = ["Structured recommendation"]
    if data.structured_instrument_id:
        parts.append(f"instrument={data.structured_instrument_id}")
    if data.structured_side:
        parts.append(f"side={data.structured_side.value}")
    if data.structured_price is not None:
        parts.append(f"price={_format_decimal(data.structured_price)}")
    if data.structured_quantity is not None:
        parts.append(f"qty={_format_decimal(data.structured_quantity)}")
    if data.structured_price is not None and data.structured_quantity is not None:
        parts.append(f"amount={_format_decimal(data.structured_price * data.structured_quantity)}")
    return " · ".join(parts)


def _attach_message(
    recommendation: Recommendation,
    data: RecommendationFormData,
    payload: dict[str, object],
    *,
    created_by_user_id: str | None = None,
) -> None:
    recommendation.messages = [_build_message(data, payload, created_by_user_id=created_by_user_id)]


async def _store_attachments(
    repository: AuthorRepository,
    recommendation: Recommendation,
    *,
    attachments: list[IncomingAttachment],
    uploaded_by_user_id: str | None,
    storage: StorageBackend,
) -> None:
    storage.bootstrap()
    for item in attachments:
        object_key = build_attachment_object_key(recommendation.id, item.filename)
        stored = storage.upload_bytes(object_key, item.data, item.content_type)
        repository.add(
            RecommendationAttachment(
                recommendation_id=recommendation.id,
                uploaded_by_user_id=uploaded_by_user_id,
                object_key=stored.object_key,
                original_filename=item.filename,
                content_type=stored.content_type,
                size_bytes=stored.size_bytes,
            )
        )
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
