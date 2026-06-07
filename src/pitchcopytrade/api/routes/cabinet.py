from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageKind, MessageModeration, MessageStatus, MessageType, RiskLevel, StrategyStatus
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.services.notifications import deliver_message_notifications_by_id
from pitchcopytrade.web.templates import templates

router = APIRouter(prefix="/cabinet", tags=["cabinet"])
logger = logging.getLogger(__name__)


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
        url=f"/cabinet/strategies/{strategy_id}/messages",
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


@router.get("/strategies/{strategy_id}/messages", response_class=HTMLResponse)
async def cabinet_recommendations_list(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    strategy = await _get_author_strategy(session, strategy_id, author.id)
    recommendations = await _list_strategy_messages(session, strategy_id)
    return templates.TemplateResponse(
        request,
        "cabinet/messages.html",
        {
            "title": strategy.title,
            "user": user,
            "author": author,
            "strategy": strategy,
            "recommendations": recommendations,
            "active_nav": "strategies",
        },
    )


@router.post("/strategies/{strategy_id}/messages", response_class=HTMLResponse)
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
        inst_result = await session.execute(select(Instrument).where(Instrument.ticker == ticker.upper()))
        instrument = inst_result.scalar_one_or_none()

    message = Message(
        strategy_id=strategy.id,
        author_id=author.id,
        kind=MessageKind.IDEA.value,
        type=MessageType.MIXED.value,
        status=MessageStatus.DRAFT.value,
        moderation=MessageModeration.REQUIRED.value,
        title=f"{side.upper()} {ticker.upper()}",
        comment=None,
        deliver=["telegram"],
        channel=["telegram", "miniapp"],
        text={},
        documents=[],
        deals=[
            {
                "instrument_id": instrument.id if instrument else None,
                "side": side.lower() if side else None,
                "entry_from": price.strip() or None,
                "take_profit_1": target.strip() or None,
                "stop_loss": stop.strip() or None,
            }
        ],
    )

    if session is not None:
        session.add(message)
        await session.commit()
        await session.refresh(message)

    return templates.TemplateResponse(
        request,
        "cabinet/message_row.html",
        {
            "rec": _cabinet_row(message, instrument=instrument),
            "strategy_id": strategy_id,
        },
    )


@router.post("/messages/{recommendation_id}/publish", response_class=HTMLResponse)
async def cabinet_recommendation_publish(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_message(session, recommendation_id, author.id)
    if rec.status != MessageStatus.DRAFT.value:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Можно публиковать только черновик")
    rec.status = MessageStatus.PUBLISHED.value
    rec.published = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)

        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        try:
            await deliver_message_notifications_by_id(session, str(rec.id), bot, trigger="cabinet_publish")
        except Exception as exc:
            logger.error("Notification delivery failed for message %s: %s", rec.id, exc)
        finally:
            await bot.session.close()

    return templates.TemplateResponse(
        request,
        "cabinet/message_row.html",
        {"rec": _cabinet_row(rec), "strategy_id": rec.strategy_id},
    )


@router.post("/messages/{recommendation_id}/close", response_class=HTMLResponse)
async def cabinet_recommendation_close(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_message(session, recommendation_id, author.id)
    rec.status = MessageStatus.CLOSED.value
    rec.archived = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)
    return templates.TemplateResponse(
        request,
        "cabinet/message_row.html",
        {"rec": _cabinet_row(rec), "strategy_id": rec.strategy_id},
    )


@router.post("/messages/{recommendation_id}/cancel", response_class=HTMLResponse)
async def cabinet_recommendation_cancel(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    author = _get_author_profile(user)
    rec = await _get_author_message(session, recommendation_id, author.id)
    rec.status = MessageStatus.CANCELLED.value
    rec.archived = datetime.now(timezone.utc)
    if session is not None:
        await session.commit()
        await session.refresh(rec)
    return templates.TemplateResponse(
        request,
        "cabinet/message_row.html",
        {"rec": _cabinet_row(rec), "strategy_id": rec.strategy_id},
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
        select(Strategy).where(Strategy.author_id == author_id).order_by(Strategy.title.asc())
    )
    return list(result.scalars().all())


async def _get_author_strategy(session, strategy_id: str, author_id: str) -> Strategy:
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    result = await session.execute(select(Strategy).where(Strategy.id == strategy_id, Strategy.author_id == author_id))
    strategy = result.scalar_one_or_none()
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    return strategy


async def _list_strategy_messages(session, strategy_id: str) -> list:
    if session is None:
        return []
    result = await session.execute(
        select(Message)
        .options(selectinload(Message.strategy))
        .where(Message.strategy_id == strategy_id)
        .order_by(Message.created.desc())
    )
    return [_cabinet_row(item) for item in result.scalars().all()]


async def _get_author_message(session, recommendation_id: str, author_id: str) -> Message:
    if session is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")
    result = await session.execute(
        select(Message).where(Message.id == recommendation_id, Message.author_id == author_id)
    )
    message = result.scalar_one_or_none()
    if message is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сообщение не найдено")
    return message


def _cabinet_row(message: Message, instrument: Instrument | None = None):
    deals = list(message.deals or [])
    leg = SimpleNamespace(
        instrument=instrument,
        side=SimpleNamespace(value=deals[0].get("side")) if deals else None,
        entry_from=deals[0].get("entry_from") if deals else None,
        take_profit_1=deals[0].get("take_profit_1") if deals else None,
        stop_loss=deals[0].get("stop_loss") if deals else None,
    )
    return SimpleNamespace(
        id=message.id,
        strategy_id=message.strategy_id,
        created_at=message.created,
        status=SimpleNamespace(value=message.status),
        legs=[leg] if deals else [],
    )
