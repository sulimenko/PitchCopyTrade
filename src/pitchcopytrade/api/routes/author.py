from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.services.author import (
    blank_leg_values,
    build_leg_rows_from_form,
    build_recommendation_form_data,
    create_author_recommendation,
    get_author_by_user,
    get_author_recommendation,
    get_author_workspace_stats,
    leg_form_values_from_rows,
    list_active_instruments,
    list_author_recommendations,
    list_author_strategies,
    normalize_attachment_uploads,
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
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    stats = await get_author_workspace_stats(repository, author)
    strategies = await list_author_strategies(repository, author)
    recommendations = await list_author_recommendations(repository, author)
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
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendations = await list_author_recommendations(repository, author)
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
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        repository=repository,
        recommendation=None,
        error=None,
        form_values=None,
    )


@router.post("/recommendations", response_class=HTMLResponse)
async def recommendation_create_submit(
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    form = await request.form()
    leg_rows = build_leg_rows_from_form(form)
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        data = build_recommendation_form_data(
            strategy_id=str(form.get("strategy_id", "") or ""),
            kind_value=str(form.get("kind", "") or ""),
            status_value=str(form.get("status", "") or ""),
            title=str(form.get("title", "") or ""),
            summary=str(form.get("summary", "") or ""),
            thesis=str(form.get("thesis", "") or ""),
            market_context=str(form.get("market_context", "") or ""),
            requires_moderation=str(form.get("requires_moderation")) if form.get("requires_moderation") else None,
            scheduled_for=str(form.get("scheduled_for", "") or ""),
            allowed_strategy_ids={item.id for item in strategies},
            allowed_instrument_ids={item.id for item in instruments},
            leg_rows=leg_rows,
            attachments=uploads,
        )
        recommendation = await create_author_recommendation(
            repository,
            author,
            data,
            uploaded_by_user_id=user.id,
        )
    except ValueError as exc:
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            repository=repository,
            recommendation=None,
            error=str(exc),
            form_values={
                "strategy_id": str(form.get("strategy_id", "") or ""),
                "kind": str(form.get("kind", "") or ""),
                "status": str(form.get("status", "") or ""),
                "title": str(form.get("title", "") or ""),
                "summary": str(form.get("summary", "") or ""),
                "thesis": str(form.get("thesis", "") or ""),
                "market_context": str(form.get("market_context", "") or ""),
                "requires_moderation": form.get("requires_moderation") is not None,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "legs": leg_form_values_from_rows(leg_rows),
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
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        repository=repository,
        recommendation=recommendation,
        error=None,
        form_values=None,
    )


@router.get("/recommendations/{recommendation_id}/preview", response_class=HTMLResponse)
async def recommendation_preview_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")
    return templates.TemplateResponse(
        request,
        "app/recommendation_detail.html",
        {
            "title": recommendation.title or recommendation.strategy.title,
            "user": user,
            "recommendation": recommendation,
            "preview_mode": True,
            "attachment_download_enabled": False,
        },
    )


@router.post("/recommendations/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_edit_submit(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found")

    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    form = await request.form()
    leg_rows = build_leg_rows_from_form(form)
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        data = build_recommendation_form_data(
            strategy_id=str(form.get("strategy_id", "") or ""),
            kind_value=str(form.get("kind", "") or ""),
            status_value=str(form.get("status", "") or ""),
            title=str(form.get("title", "") or ""),
            summary=str(form.get("summary", "") or ""),
            thesis=str(form.get("thesis", "") or ""),
            market_context=str(form.get("market_context", "") or ""),
            requires_moderation=str(form.get("requires_moderation")) if form.get("requires_moderation") else None,
            scheduled_for=str(form.get("scheduled_for", "") or ""),
            allowed_strategy_ids={item.id for item in strategies},
            allowed_instrument_ids={item.id for item in instruments},
            leg_rows=leg_rows,
            attachments=uploads,
        )
        await update_author_recommendation(
            repository,
            recommendation,
            data,
            uploaded_by_user_id=user.id,
        )
    except ValueError as exc:
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            repository=repository,
            recommendation=recommendation,
            error=str(exc),
            form_values={
                "strategy_id": str(form.get("strategy_id", "") or ""),
                "kind": str(form.get("kind", "") or ""),
                "status": str(form.get("status", "") or ""),
                "title": str(form.get("title", "") or ""),
                "summary": str(form.get("summary", "") or ""),
                "thesis": str(form.get("thesis", "") or ""),
                "market_context": str(form.get("market_context", "") or ""),
                "requires_moderation": form.get("requires_moderation") is not None,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "legs": leg_form_values_from_rows(leg_rows),
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
    repository: AuthorRepository,
    recommendation,
    error: str | None,
    form_values: dict[str, object] | None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    strategies = await list_author_strategies(repository, author)
    effective_form_values = form_values or recommendation_form_values(recommendation)
    instruments = await list_active_instruments(repository)
    return templates.TemplateResponse(
        request,
        "author/recommendation_form.html",
        {
            "title": "Редактор рекомендации" if recommendation else "Новая рекомендация",
            "user": user,
            "author": author,
            "recommendation": recommendation,
            "strategies": strategies,
            "instruments": instruments,
            "recommendation_kind_options": ["new_idea", "update", "close", "cancel"],
            "recommendation_status_options": [
                "draft",
                "review",
                "approved",
                "scheduled",
                "published",
                "closed",
                "cancelled",
                "archived",
            ],
            "error": error,
            "form_values": effective_form_values,
            "blank_leg_values": blank_leg_values(),
        },
        status_code=status_code,
    )


async def _get_author_or_403(repository: AuthorRepository, user: User) -> AuthorProfile:
    author = user.author_profile or await get_author_by_user(repository, user)
    if author is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Author profile is not configured")
    return author
