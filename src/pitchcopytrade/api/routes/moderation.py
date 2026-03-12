from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from pitchcopytrade.api.deps.auth import require_moderator
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore
from pitchcopytrade.services.moderation import (
    approve_recommendation,
    build_moderation_detail_metrics,
    get_moderation_queue_stats,
    get_moderation_recommendation,
    list_recommendation_audit_events,
    list_moderation_recommendations,
    reject_recommendation,
    send_recommendation_to_rework,
)
from pitchcopytrade.services.notifications import deliver_recommendation_notifications, deliver_recommendation_notifications_file
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/moderation", tags=["moderation"])


@router.get("", include_in_schema=False)
async def moderation_root() -> Response:
    return RedirectResponse(url="/moderation/queue", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/queue", response_class=HTMLResponse)
async def moderation_queue_page(
    request: Request,
    q: str = "",
    status_value: str = "",
    user: User = Depends(require_moderator),
    session=Depends(get_optional_db_session),
) -> Response:
    if q or status_value:
        items = await list_moderation_recommendations(
            session,
            status_filter=_parse_queue_status(status_value),
            query_text=q,
        )
    else:
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
            "query_text": q,
            "status_value": status_value,
            "status_options": ["review", "approved", "scheduled", "published"],
        },
    )


@router.get("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def moderation_detail_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_moderator),
    session=Depends(get_optional_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    history = await list_recommendation_audit_events(session, recommendation_id)
    metrics = build_moderation_detail_metrics(recommendation, history)
    return templates.TemplateResponse(
        request,
        "moderation/detail.html",
        {
            "title": recommendation.title or "Recommendation moderation",
            "user": user,
            "recommendation": recommendation,
            "history": history,
            "metrics": metrics,
        },
    )


@router.post("/recommendations/{recommendation_id}/approve")
async def moderation_approve_submit(
    recommendation_id: str,
    comment: str = Form(""),
    user: User = Depends(require_moderator),
    session=Depends(get_optional_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    updated = await approve_recommendation(session, recommendation, user, comment)
    if updated.status.value == "published":
        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        try:
            if session is None:
                store = FileDataStore()
                graph = FileDatasetGraph.load(store)
                latest = graph.recommendations.get(updated.id)
                if latest is not None:
                    await deliver_recommendation_notifications_file(graph, store, latest, bot)
            else:
                await deliver_recommendation_notifications(session, updated, bot)
        finally:
            await bot.session.close()
    return RedirectResponse(url=f"/moderation/recommendations/{recommendation_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/recommendations/{recommendation_id}/rework")
async def moderation_rework_submit(
    recommendation_id: str,
    comment: str = Form(...),
    user: User = Depends(require_moderator),
    session=Depends(get_optional_db_session),
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
    session=Depends(get_optional_db_session),
) -> Response:
    recommendation = await get_moderation_recommendation(session, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    await reject_recommendation(session, recommendation, user, comment)
    return RedirectResponse(url=f"/moderation/recommendations/{recommendation_id}", status_code=status.HTTP_303_SEE_OTHER)


def _parse_queue_status(status_value: str):
    normalized = status_value.strip().lower()
    if not normalized:
        return None
    from pitchcopytrade.db.models.enums import RecommendationStatus

    try:
        return RecommendationStatus(normalized)
    except ValueError:
        return None
