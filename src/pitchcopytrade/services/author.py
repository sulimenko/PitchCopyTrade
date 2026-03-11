from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus


@dataclass(slots=True)
class AuthorWorkspaceStats:
    strategies_total: int
    recommendations_total: int
    draft_recommendations: int
    live_recommendations: int


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


async def get_author_workspace_stats(session: AsyncSession, author: AuthorProfile) -> AuthorWorkspaceStats:
    strategies_total = await _count_query(
        session,
        select(func.count(Strategy.id)).where(Strategy.author_id == author.id),
    )
    recommendations_total = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(Recommendation.author_id == author.id),
    )
    draft_recommendations = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(
            Recommendation.author_id == author.id,
            Recommendation.status == RecommendationStatus.DRAFT,
        ),
    )
    live_recommendations = await _count_query(
        session,
        select(func.count(Recommendation.id)).where(
            Recommendation.author_id == author.id,
            Recommendation.status.in_(
                [
                    RecommendationStatus.PUBLISHED,
                    RecommendationStatus.SCHEDULED,
                    RecommendationStatus.APPROVED,
                ]
            ),
        ),
    )
    return AuthorWorkspaceStats(
        strategies_total=strategies_total,
        recommendations_total=recommendations_total,
        draft_recommendations=draft_recommendations,
        live_recommendations=live_recommendations,
    )


async def list_author_strategies(session: AsyncSession, author: AuthorProfile) -> list[Strategy]:
    query = (
        select(Strategy)
        .where(Strategy.author_id == author.id)
        .order_by(Strategy.title.asc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def list_author_recommendations(session: AsyncSession, author: AuthorProfile) -> list[Recommendation]:
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy),
            selectinload(Recommendation.legs),
            selectinload(Recommendation.attachments),
        )
        .where(Recommendation.author_id == author.id)
        .order_by(Recommendation.updated_at.desc(), Recommendation.created_at.desc())
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_author_recommendation(
    session: AsyncSession,
    author: AuthorProfile,
    recommendation_id: str,
) -> Recommendation | None:
    query = (
        select(Recommendation)
        .options(
            selectinload(Recommendation.strategy),
            selectinload(Recommendation.legs),
            selectinload(Recommendation.attachments),
        )
        .where(
            Recommendation.id == recommendation_id,
            Recommendation.author_id == author.id,
        )
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def create_author_recommendation(
    session: AsyncSession,
    author: AuthorProfile,
    data: RecommendationFormData,
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
    _apply_terminal_dates(recommendation)
    session.add(recommendation)
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def update_author_recommendation(
    session: AsyncSession,
    recommendation: Recommendation,
    data: RecommendationFormData,
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
    _apply_terminal_dates(recommendation)
    await session.commit()
    await session.refresh(recommendation)
    return recommendation


async def get_author_by_user(session: AsyncSession, user: User) -> AuthorProfile | None:
    query = (
        select(AuthorProfile)
        .options(selectinload(AuthorProfile.user))
        .where(AuthorProfile.user_id == user.id)
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


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
    )


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
        }

    scheduled_for = ""
    if recommendation.scheduled_for is not None:
        scheduled_for = recommendation.scheduled_for.strftime("%Y-%m-%dT%H:%M")

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
    }


def _apply_terminal_dates(recommendation: Recommendation) -> None:
    now = datetime.now(timezone.utc)
    if recommendation.status == RecommendationStatus.PUBLISHED and recommendation.published_at is None:
        recommendation.published_at = now
    elif recommendation.status != RecommendationStatus.PUBLISHED:
        recommendation.published_at = None

    recommendation.closed_at = now if recommendation.status == RecommendationStatus.CLOSED else None
    recommendation.cancelled_at = now if recommendation.status == RecommendationStatus.CANCELLED else None


def _parse_datetime_local(value: str) -> datetime:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError as exc:
        raise ValueError("Некорректный формат даты. Используйте YYYY-MM-DDTHH:MM.") from exc


async def _count_query(session: AsyncSession, query) -> int:
    result = await session.execute(query)
    return int(result.scalar_one())
