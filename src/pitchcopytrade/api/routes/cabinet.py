from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal

logger = logging.getLogger(__name__)

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, RiskLevel, StrategyStatus, TradeSide
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.web.templates import templates

router = APIRouter(prefix="/cabinet", tags=["cabinet"])


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-")[:120]


def _get_author_profile(user: User):
    if user.author_profile is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Author profile not found")
    return user.author_profile


@router.get("", response_class=HTMLResponse, include_in_schema=False)
async def cabinet_root(user: User = Depends(require_author)) -> Response:
    return RedirectResponse(url="/cabinet/strategies", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/strategies", response_class=HTMLResponse)
async def cabinet_strategies(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    strategies = await _list_author_strategies(session, author.id)
    return templates.TemplateResponse(
        request,
        "cabinet/strategies.html",
        {
            "title": "Стратегии",
            "user": user,
            "author": author,
            "strategies": strategies,
            "active_nav": "strategies",
        },
    )


@router.post("/strategies", response_class=HTMLResponse)
async def cabinet_strategy_create(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
    title: str = Form(...),
    short_description: str = Form(""),
    risk_level: str = Form("medium"),
) -> Response:
    author = _get_author_profile(user)
    slug = _slugify(title)
    if session is not None:
        existing = await session.execute(select(Strategy).where(Strategy.slug == slug))
        if existing.scalar_one_or_none() is not None:
            slug = f"{slug}-{str(uuid.uuid4())[:8]}"
        strategy = Strategy(
            author_id=author.id,
            slug=slug,
            title=title.strip(),
            short_description=short_description.strip(),
            risk_level=RiskLevel(risk_level),
            status=StrategyStatus.DRAFT,
        )
        session.add(strategy)
        await session.commit()
    return RedirectResponse(url="/cabinet/strategies", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/strategies/{strategy_id}", response_class=HTMLResponse, include_in_schema=False)
async def cabinet_strategy_redirect(
    strategy_id: str,
    user: User = Depends(require_author),
) -> Response:
    return RedirectResponse(
        url=f"/cabinet/strategies/{strategy_id}/recommendations",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/strategies/{strategy_id}/edit", response_class=HTMLResponse)
async def cabinet_strategy_edit_page(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    strategy = await _get_author_strategy(session, strategy_id, author.id)
    return templates.TemplateResponse(
        request,
        "cabinet/strategy_edit.html",
        {
            "title": strategy.title,
            "user": user,
            "author": author,
            "strategy": strategy,
            "error": None,
            "active_nav": "strategies",
        },
    )


@router.post("/strategies/{strategy_id}/edit", response_class=HTMLResponse)
async def cabinet_strategy_edit_save(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
    title: str = Form(...),
    short_description: str = Form(""),
    risk_level: str = Form("medium"),
    min_capital_rub: str = Form(""),
) -> Response:
    author = _get_author_profile(user)
    strategy = await _get_author_strategy(session, strategy_id, author.id)
    strategy.title = title.strip()
    strategy.short_description = short_description.strip()
    strategy.risk_level = RiskLevel(risk_level)
    strategy.min_capital_rub = int(min_capital_rub) if min_capital_rub.strip() else None
    if session is not None:
        await session.commit()
    return RedirectResponse(url="/cabinet/strategies", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/strategies/{strategy_id}/recommendations", response_class=HTMLResponse)
async def cabinet_recommendations_list(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    strategy = await _get_author_strategy(session, strategy_id, author.id)
    recommendations = await _list_strategy_recommendations(session, strategy_id)
    return templates.TemplateResponse(
        request,
        "cabinet/recommendations.html",
        {
            "title": strategy.title,
            "user": user,
            "author": author,
            "strategy": strategy,
            "recommendations": recommendations,
            "active_nav": "strategies",
        },
    )


@router.post("/strategies/{strategy_id}/recommendations", response_class=HTMLResponse)
async def cabinet_recommendation_create(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
    ticker: str = Form(...),
    side: str = Form(...),
    price: str = Form(""),
    target: str = Form(""),
    stop: str = Form(""),
) -> Response:
    author = _get_author_profile(user)
    strategy = await _get_author_strategy(session, strategy_id, author.id)

    instrument = None
    if session is not None:
        inst_result = await session.execute(
            select(Instrument).where(Instrument.ticker == ticker.upper())
        )
        instrument = inst_result.scalar_one_or_none()

    rec = Recommendation(
        strategy_id=strategy.id,
        author_id=author.id,
        kind=RecommendationKind.NEW_IDEA,
        status=RecommendationStatus.DRAFT,
        requires_moderation=False,
    )

    if session is not None:
        session.add(rec)
        await session.flush()

        leg = RecommendationLeg(
            recommendation_id=rec.id,
            instrument_id=instrument.id if instrument else None,
            side=TradeSide(side.lower()) if side else None,
            entry_from=_parse_decimal(price),
            take_profit_1=_parse_decimal(target),
            stop_loss=_parse_decimal(stop),
        )
        session.add(leg)
        await session.commit()
        await session.refresh(rec)
        # Reload with legs+instrument
        rec_result = await session.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument))
            .where(Recommendation.id == rec.id)
        )
        rec = rec_result.scalar_one()

    return templates.TemplateResponse(
        request,
        "cabinet/recommendation_row.html",
        {
            "rec": rec,
            "strategy_id": strategy_id,
        },
    )


@router.post("/recommendations/{recommendation_id}/publish", response_class=HTMLResponse)
async def cabinet_recommendation_publish(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_recommendation(session, recommendation_id, author.id)
    if rec.status != RecommendationStatus.DRAFT:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Можно публиковать только черновик")
    rec.status = RecommendationStatus.PUBLISHED
    rec.published_at = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)
        rec_result = await session.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument))
            .where(Recommendation.id == rec.id)
        )
        rec = rec_result.scalar_one()

    # Enqueue ARQ job (fire-and-forget: публикация не блокируется если worker упал)
    arq_pool = getattr(request.app.state, "arq_pool", None)
    if arq_pool is not None:
        try:
            await arq_pool.enqueue_job("send_recommendation_notifications", str(rec.id))
        except Exception as exc:
            logger.error("ARQ enqueue failed for rec %s: %s", rec.id, exc)

    return templates.TemplateResponse(
        request,
        "cabinet/recommendation_row.html",
        {"rec": rec, "strategy_id": rec.strategy_id},
    )


@router.post("/recommendations/{recommendation_id}/close", response_class=HTMLResponse)
async def cabinet_recommendation_close(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_recommendation(session, recommendation_id, author.id)
    rec.status = RecommendationStatus.CLOSED
    rec.closed_at = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)
        rec_result = await session.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument))
            .where(Recommendation.id == rec.id)
        )
        rec = rec_result.scalar_one()
    return templates.TemplateResponse(
        request,
        "cabinet/recommendation_row.html",
        {"rec": rec, "strategy_id": rec.strategy_id},
    )


@router.post("/recommendations/{recommendation_id}/cancel", response_class=HTMLResponse)
async def cabinet_recommendation_cancel(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_recommendation(session, recommendation_id, author.id)
    rec.status = RecommendationStatus.CANCELLED
    rec.cancelled_at = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)
        rec_result = await session.execute(
            select(Recommendation)
            .options(selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument))
            .where(Recommendation.id == rec.id)
        )
        rec = rec_result.scalar_one()
    return templates.TemplateResponse(
        request,
        "cabinet/recommendation_row.html",
        {"rec": rec, "strategy_id": rec.strategy_id},
    )


def _parse_decimal(value: str):
    value = value.strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


async def _list_author_strategies(session, author_id: str) -> list:
    if session is None:
        return []
    result = await session.execute(
        select(Strategy)
        .where(Strategy.author_id == author_id)
        .order_by(Strategy.title.asc())
    )
    return list(result.scalars().all())


async def _get_author_strategy(session, strategy_id: str, author_id: str) -> Strategy:
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    result = await session.execute(
        select(Strategy).where(Strategy.id == strategy_id, Strategy.author_id == author_id)
    )
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    return strategy


async def _list_strategy_recommendations(session, strategy_id: str) -> list:
    if session is None:
        return []
    result = await session.execute(
        select(Recommendation)
        .options(selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument))
        .where(Recommendation.strategy_id == strategy_id)
        .order_by(Recommendation.created_at.desc())
    )
    return list(result.scalars().all())


async def _get_author_recommendation(session, recommendation_id: str, author_id: str) -> Recommendation:
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рекомендация не найдена")
    result = await session.execute(
        select(Recommendation)
        .where(Recommendation.id == recommendation_id, Recommendation.author_id == author_id)
    )
    rec = result.scalar_one_or_none()
    if rec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рекомендация не найдена")
    return rec
