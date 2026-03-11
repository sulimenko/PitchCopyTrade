from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable
from uuid import uuid4

from starlette.datastructures import UploadFile

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, TradeSide
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.storage.base import StorageBackend
from pitchcopytrade.storage.minio import MinioStorage

MAX_EDITOR_LEGS = 3
MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}


@dataclass(slots=True)
class AuthorWorkspaceStats:
    strategies_total: int
    recommendations_total: int
    draft_recommendations: int
    live_recommendations: int


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


async def list_active_instruments(repository: AuthorRepository) -> list[Instrument]:
    return await repository.list_active_instruments()


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
    recommendation = Recommendation(
        author_id=author.id,
        strategy_id=data.strategy_id,
        kind=data.kind,
        status=data.status,
        title=data.title,
        summary=data.summary,
        thesis=data.thesis,
        market_context=data.market_context,
        requires_moderation=data.requires_moderation,
        scheduled_for=data.scheduled_for,
    )
    _apply_publish_state(recommendation)
    repository.add(recommendation)
    await repository.flush()
    _attach_legs(recommendation, data.legs)
    if data.attachments:
        await _store_attachments(
            repository,
            recommendation,
            attachments=data.attachments,
            uploaded_by_user_id=uploaded_by_user_id,
            storage=storage or MinioStorage(),
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
    recommendation.strategy_id = data.strategy_id
    recommendation.kind = data.kind
    recommendation.status = data.status
    recommendation.title = data.title
    recommendation.summary = data.summary
    recommendation.thesis = data.thesis
    recommendation.market_context = data.market_context
    recommendation.requires_moderation = data.requires_moderation
    recommendation.scheduled_for = data.scheduled_for
    _apply_publish_state(recommendation)
    await _replace_legs(repository, recommendation, data.legs)
    if data.attachments:
        await _store_attachments(
            repository,
            recommendation,
            attachments=data.attachments,
            uploaded_by_user_id=uploaded_by_user_id,
            storage=storage or MinioStorage(),
        )
    await repository.commit()
    await repository.refresh(recommendation)
    return recommendation


async def get_author_by_user(repository: AuthorRepository, user: User) -> AuthorProfile | None:
    return await repository.get_author_by_user_id(user.id)


def build_recommendation_form_data(
    *,
    strategy_id: str,
    kind_value: str,
    status_value: str,
    title: str,
    summary: str,
    thesis: str,
    market_context: str,
    requires_moderation: str | None,
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

    legs = _build_leg_rows(leg_rows, allowed_instrument_ids)
    parsed_attachments = list(attachments)

    return RecommendationFormData(
        strategy_id=normalized_strategy_id,
        kind=kind,
        status=status,
        title=title.strip() or None,
        summary=summary.strip() or None,
        thesis=thesis.strip() or None,
        market_context=market_context.strip() or None,
        requires_moderation=requires_moderation is not None,
        scheduled_for=scheduled_for_value,
        legs=legs,
        attachments=parsed_attachments,
    )


async def normalize_attachment_uploads(files: Iterable[UploadFile]) -> list[IncomingAttachment]:
    uploads: list[IncomingAttachment] = []
    for item in files:
        filename = (item.filename or "").strip()
        if not filename:
            continue
        content_type = (item.content_type or "application/octet-stream").strip()
        if content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
            raise ValueError("Разрешены только PDF и изображения JPG/PNG/WEBP.")
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
            "legs": _blank_leg_values(),
        }

    scheduled_for = ""
    if recommendation.scheduled_for is not None:
        scheduled_for = recommendation.scheduled_for.strftime("%Y-%m-%dT%H:%M")

    legs = _blank_leg_values()
    for index, leg in enumerate(recommendation.legs[:MAX_EDITOR_LEGS]):
        legs[index] = {
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
    }


def blank_leg_values() -> list[dict[str, str]]:
    return _blank_leg_values()


def build_leg_rows_from_form(form) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index in range(MAX_EDITOR_LEGS):
        rows.append(
            {
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
    values = _blank_leg_values()
    for index, row in enumerate(rows[:MAX_EDITOR_LEGS]):
        values[index] = {
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
    return values


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


def _build_leg_rows(rows: Iterable[dict[str, str]], allowed_instrument_ids: set[str]) -> list[StructuredLegFormData]:
    legs: list[StructuredLegFormData] = []
    for index, row in enumerate(rows, start=1):
        if not any((value or "").strip() for value in row.values()):
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

        if entry_from is None and entry_to is None and stop_loss is None and take_profit_1 is None:
            raise ValueError(f"Leg {index}: заполните хотя бы entry/stop/take.")

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
                storage_provider=storage.provider_name,
                bucket_name=stored.bucket_name,
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


def _blank_leg_values() -> list[dict[str, str]]:
    return [
        {
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
        for _ in range(MAX_EDITOR_LEGS)
    ]
