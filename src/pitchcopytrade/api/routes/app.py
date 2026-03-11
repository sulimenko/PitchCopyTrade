from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import get_current_subscriber_user
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.services.acl import (
    get_user_visible_recommendation,
    list_user_visible_recommendations,
    user_has_active_access,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/app", tags=["app"])


@router.get("/feed", response_class=HTMLResponse)
async def app_feed(
    request: Request,
    user: User = Depends(get_current_subscriber_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendations = await list_user_visible_recommendations(session, user_id=user.id)
    has_access = await user_has_active_access(session, user_id=user.id)
    return templates.TemplateResponse(
        request,
        "app/feed.html",
        {
            "title": "Лента рекомендаций",
            "user": user,
            "recommendations": recommendations,
            "has_access": has_access,
        },
    )


@router.get("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_detail_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(get_current_subscriber_user),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendation = await get_user_visible_recommendation(
        session,
        user_id=user.id,
        recommendation_id=recommendation_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return templates.TemplateResponse(
        request,
        "app/recommendation_detail.html",
        {
            "title": recommendation.title or "Рекомендация",
            "user": user,
            "recommendation": recommendation,
        },
    )
