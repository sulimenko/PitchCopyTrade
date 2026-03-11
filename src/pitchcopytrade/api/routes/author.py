from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.services.author import (
    build_recommendation_form_data,
    create_author_recommendation,
    get_author_by_user,
    get_author_recommendation,
    get_author_workspace_stats,
    list_author_recommendations,
    list_author_strategies,
    recommendation_form_values,
    update_author_recommendation,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/author", tags=["author"])


@router.get("", include_in_schema=False)
async def author_root() -> Response:
    return RedirectResponse(url="/author/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dashboard", response_class=HTMLResponse)
async def author_dashboard(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    author = await _get_author_or_403(session, user)
    stats = await get_author_workspace_stats(session, author)
    strategies = await list_author_strategies(session, author)
    recommendations = await list_author_recommendations(session, author)
    return templates.TemplateResponse(
        request,
        "author/dashboard.html",
        {
            "title": "Author Workspace",
            "user": user,
            "author": author,
            "stats": stats,
            "strategies": strategies[:5],
            "recommendations": recommendations[:6],
        },
    )


@router.get("/recommendations", response_class=HTMLResponse)
async def recommendation_list_page(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    author = await _get_author_or_403(session, user)
    recommendations = await list_author_recommendations(session, author)
    return templates.TemplateResponse(
        request,
        "author/recommendations_list.html",
        {
            "title": "Рекомендации автора",
            "user": user,
            "author": author,
            "recommendations": recommendations,
        },
    )


@router.get("/recommendations/new", response_class=HTMLResponse)
async def recommendation_create_page(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    author = await _get_author_or_403(session, user)
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        session=session,
        recommendation=None,
        error=None,
        form_values=None,
    )


@router.post("/recommendations", response_class=HTMLResponse)
async def recommendation_create_submit(
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
    strategy_id: str = Form(...),
    kind: str = Form(...),
    status_value: str = Form(..., alias="status"),
    title: str = Form(""),
    summary: str = Form(""),
    thesis: str = Form(""),
    market_context: str = Form(""),
    requires_moderation: str | None = Form(default=None),
    scheduled_for: str = Form(""),
) -> Response:
    author = await _get_author_or_403(session, user)
    strategies = await list_author_strategies(session, author)
    try:
        data = build_recommendation_form_data(
            strategy_id=strategy_id,
            kind_value=kind,
            status_value=status_value,
            title=title,
            summary=summary,
            thesis=thesis,
            market_context=market_context,
            requires_moderation=requires_moderation,
            scheduled_for=scheduled_for,
            allowed_strategy_ids={item.id for item in strategies},
        )
        recommendation = await create_author_recommendation(session, author, data)
    except ValueError as exc:
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            session=session,
            recommendation=None,
            error=str(exc),
            form_values={
                "strategy_id": strategy_id,
                "kind": kind,
                "status": status_value,
                "title": title,
                "summary": summary,
                "thesis": thesis,
                "market_context": market_context,
                "requires_moderation": requires_moderation is not None,
                "scheduled_for": scheduled_for,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(
        url=f"/author/recommendations/{recommendation.id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/recommendations/{recommendation_id}/edit", response_class=HTMLResponse)
async def recommendation_edit_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    author = await _get_author_or_403(session, user)
    recommendation = await get_author_recommendation(session, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        session=session,
        recommendation=recommendation,
        error=None,
        form_values=None,
    )


@router.post("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_edit_submit(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    session: AsyncSession = Depends(get_db_session),
    strategy_id: str = Form(...),
    kind: str = Form(...),
    status_value: str = Form(..., alias="status"),
    title: str = Form(""),
    summary: str = Form(""),
    thesis: str = Form(""),
    market_context: str = Form(""),
    requires_moderation: str | None = Form(default=None),
    scheduled_for: str = Form(""),
) -> Response:
    author = await _get_author_or_403(session, user)
    recommendation = await get_author_recommendation(session, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    strategies = await list_author_strategies(session, author)
    try:
        data = build_recommendation_form_data(
            strategy_id=strategy_id,
            kind_value=kind,
            status_value=status_value,
            title=title,
            summary=summary,
            thesis=thesis,
            market_context=market_context,
            requires_moderation=requires_moderation,
            scheduled_for=scheduled_for,
            allowed_strategy_ids={item.id for item in strategies},
        )
        await update_author_recommendation(session, recommendation, data)
    except ValueError as exc:
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            session=session,
            recommendation=recommendation,
            error=str(exc),
            form_values={
                "strategy_id": strategy_id,
                "kind": kind,
                "status": status_value,
                "title": title,
                "summary": summary,
                "thesis": thesis,
                "market_context": market_context,
                "requires_moderation": requires_moderation is not None,
                "scheduled_for": scheduled_for,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return RedirectResponse(
        url=f"/author/recommendations/{recommendation.id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


async def _render_recommendation_form(
    *,
    request: Request,
    user: User,
    author: AuthorProfile,
    session: AsyncSession,
    recommendation,
    error: str | None,
    form_values: dict[str, object] | None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    strategies = await list_author_strategies(session, author)
    effective_form_values = form_values or recommendation_form_values(recommendation)
    return templates.TemplateResponse(
        request,
        "author/recommendation_form.html",
        {
            "title": "Редактор рекомендации" if recommendation else "Новая рекомендация",
            "user": user,
            "author": author,
            "recommendation": recommendation,
            "strategies": strategies,
            "recommendation_kind_options": [item.value for item in RecommendationKind],
            "recommendation_status_options": [item.value for item in RecommendationStatus],
            "error": error,
            "form_values": effective_form_values,
        },
        status_code=status_code,
    )


async def _get_author_or_403(session: AsyncSession, user: User) -> AuthorProfile:
    author = user.author_profile or await get_author_by_user(session, user)
    if author is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Author profile is not configured")
    return author
