from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import require_moderator
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.services.moderation import (
    approve_recommendation,
    get_moderation_queue_stats,
    get_moderation_recommendation,
    list_recommendation_audit_events,
    list_moderation_recommendations,
    reject_recommendation,
    send_recommendation_to_rework,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("", include_in_schema=False)
async def moderation_root() -> Response:
    return RedirectResponse(url="/moderation/queue", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/queue", response_class=HTMLResponse)
async def moderation_queue_page(
    request: Request,
    user: User = Depends(require_moderator),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    items = await list_moderation_recommendations(session)
    stats = await get_moderation_queue_stats(session)
    return templates.TemplateResponse(
        request,
        "moderation/queue.html",
        {
            "title": "Moderation Queue",
            "user": user,
            "items": items,
            "stats": stats,
        },
    )


@router.get("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def moderation_detail_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_moderator),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    history = await list_recommendation_audit_events(session, recommendation_id)
    return templates.TemplateResponse(
        request,
        "moderation/detail.html",
        {
            "title": recommendation.title or "Recommendation moderation",
            "user": user,
            "recommendation": recommendation,
            "history": history,
        },
    )


@router.post("/recommendations/{recommendation_id}/approve")
async def moderation_approve_submit(
    recommendation_id: str,
    comment: str = Form(""),
    user: User = Depends(require_moderator),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    await approve_recommendation(session, recommendation, user, comment)
    return RedirectResponse(url=f"/moderation/recommendations/{recommendation_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/recommendations/{recommendation_id}/rework")
async def moderation_rework_submit(
    recommendation_id: str,
    comment: str = Form(...),
    user: User = Depends(require_moderator),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    await send_recommendation_to_rework(session, recommendation, user, comment)
    return RedirectResponse(url=f"/moderation/recommendations/{recommendation_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/recommendations/{recommendation_id}/reject")
async def moderation_reject_submit(
    recommendation_id: str,
    comment: str = Form(...),
    user: User = Depends(require_moderator),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    await reject_recommendation(session, recommendation, user, comment)
    return RedirectResponse(url=f"/moderation/recommendations/{recommendation_id}", status_code=status.HTTP_303_SEE_OTHER)
