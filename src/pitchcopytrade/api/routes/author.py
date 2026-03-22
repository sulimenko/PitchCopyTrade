from __future__ import annotations

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.enums import RecommendationStatus
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.repositories.author import FileAuthorRepository, SqlAlchemyAuthorRepository
from pitchcopytrade.services.author import (
    WatchlistCandidate,
    add_author_watchlist_instrument,
    build_author_strategy_form_data,
    build_leg_rows_from_form,
    build_recommendation_form_data,
    create_author_recommendation,
    create_author_strategy,
    get_author_by_user,
    get_author_recommendation,
    get_author_strategy,
    get_author_workspace_stats,
    leg_form_values_from_rows,
    list_active_instruments,
    list_author_recommendations,
    list_author_strategies,
    list_author_watchlist,
    normalize_attachment_uploads,
    remove_recommendation_attachments,
    remove_author_watchlist_instrument,
    recommendation_form_values,
    search_author_watchlist_candidates,
    update_author_recommendation,
    update_author_strategy,
)
from pitchcopytrade.services.notifications import (
    deliver_recommendation_notifications,
    deliver_recommendation_notifications_file,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/author", tags=["author"])
logger = logging.getLogger(__name__)


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
    watchlist = await list_author_watchlist(repository, author)
    instruments = await list_active_instruments(repository)
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
            "watchlist": watchlist,
            "watchlist_items": [_instrument_payload(item) for item in watchlist],
            "strategies_all": strategies,
            "instruments": instruments,
            "recommendation_modal_url": "/author/recommendations/new?embedded=1&next=/author/dashboard",
        },
    )


@router.get("/strategies", response_class=HTMLResponse)
async def author_strategy_list_page(
    request: Request,
    q: str = "",
    sort_by: str = "title",
    direction: str = "asc",
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategies = await list_author_strategies(repository, author)
    strategies = _filter_author_strategies(strategies, q=q)
    strategies = _sort_author_strategies(strategies, sort_by=sort_by, direction=direction)
    return templates.TemplateResponse(
        request,
        "author/strategies_list.html",
        {
            "title": "Стратегии автора",
            "user": user,
            "author": author,
            "strategies": strategies,
            "q": q,
            "sort_by": sort_by,
            "direction": direction,
        },
    )


@router.get("/strategies/new", response_class=HTMLResponse)
async def author_strategy_create_page(
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    return templates.TemplateResponse(
        request,
        "author/strategy_form.html",
        {
            "title": "Новая стратегия",
            "user": user,
            "author": author,
            "strategy": None,
            "error": None,
            "risk_levels": ["low", "medium", "high"],
            "form_values": {
                "title": "",
                "slug": "",
                "short_description": "",
                "risk_level": "medium",
                "min_capital_rub": "",
            },
        },
    )


@router.post("/strategies", response_class=HTMLResponse)
async def author_strategy_create_submit(
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategies = await list_author_strategies(repository, author)
    form = await request.form()
    try:
        data = build_author_strategy_form_data(
            title=str(form.get("title", "") or ""),
            slug=str(form.get("slug", "") or ""),
            short_description=str(form.get("short_description", "") or ""),
            risk_level_value=str(form.get("risk_level", "") or "medium"),
            min_capital_rub=str(form.get("min_capital_rub", "") or ""),
            existing_strategies=strategies,
        )
        strategy = await create_author_strategy(repository, author, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "author/strategy_form.html",
            {
                "title": "Новая стратегия",
                "user": user,
                "author": author,
                "strategy": None,
                "error": str(exc),
                "risk_levels": ["low", "medium", "high"],
                "form_values": {
                    "title": str(form.get("title", "") or ""),
                    "slug": str(form.get("slug", "") or ""),
                    "short_description": str(form.get("short_description", "") or ""),
                    "risk_level": str(form.get("risk_level", "") or "medium"),
                    "min_capital_rub": str(form.get("min_capital_rub", "") or ""),
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/author/strategies", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/strategies/{strategy_id}/edit", response_class=HTMLResponse)
async def author_strategy_edit_page(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategy = await get_author_strategy(repository, author, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return templates.TemplateResponse(
        request,
        "author/strategy_form.html",
        {
            "title": strategy.title,
            "user": user,
            "author": author,
            "strategy": strategy,
            "error": None,
            "risk_levels": ["low", "medium", "high"],
            "form_values": {
                "title": strategy.title,
                "slug": strategy.slug,
                "short_description": strategy.short_description,
                "risk_level": strategy.risk_level.value,
                "min_capital_rub": strategy.min_capital_rub or "",
            },
        },
    )


@router.post("/strategies/{strategy_id}", response_class=HTMLResponse)
async def author_strategy_edit_submit(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategy = await get_author_strategy(repository, author, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    strategies = await list_author_strategies(repository, author)
    form = await request.form()
    try:
        data = build_author_strategy_form_data(
            title=str(form.get("title", "") or ""),
            slug=str(form.get("slug", "") or ""),
            short_description=str(form.get("short_description", "") or ""),
            risk_level_value=str(form.get("risk_level", "") or "medium"),
            min_capital_rub=str(form.get("min_capital_rub", "") or ""),
            existing_strategies=strategies,
            current_strategy_id=strategy.id,
        )
        await update_author_strategy(repository, strategy, data)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "author/strategy_form.html",
            {
                "title": strategy.title,
                "user": user,
                "author": author,
                "strategy": strategy,
                "error": str(exc),
                "risk_levels": ["low", "medium", "high"],
                "form_values": {
                    "title": str(form.get("title", "") or ""),
                    "slug": str(form.get("slug", "") or ""),
                    "short_description": str(form.get("short_description", "") or ""),
                    "risk_level": str(form.get("risk_level", "") or "medium"),
                    "min_capital_rub": str(form.get("min_capital_rub", "") or ""),
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/author/strategies/{strategy.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/watchlist/search")
async def author_watchlist_search(
    q: str = "",
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    candidates = await search_author_watchlist_candidates(repository, author, q)
    return JSONResponse(
        {
            "query": q,
            "items": [_watchlist_candidate_payload(item) for item in candidates],
        }
    )


@router.post("/watchlist/items")
async def author_watchlist_add_item(
    instrument_id: str = Form(...),
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    try:
        instrument = await add_author_watchlist_instrument(repository, author, instrument_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    watchlist = await list_author_watchlist(repository, author)
    return JSONResponse(
        {
            "added": _instrument_payload(instrument),
            "watchlist": [_instrument_payload(item) for item in watchlist],
        }
    )


@router.post("/watchlist/items/{instrument_id}/remove")
async def author_watchlist_remove_item(
    instrument_id: str,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    try:
        await remove_author_watchlist_instrument(repository, author, instrument_id.strip())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    watchlist = await list_author_watchlist(repository, author)
    return JSONResponse(
        {
            "removed_id": instrument_id,
            "watchlist": [_instrument_payload(item) for item in watchlist],
        }
    )


@router.get("/recommendations", response_class=HTMLResponse)
async def recommendation_list_page(
    request: Request,
    q: str = "",
    status_filter: str = "all",
    sort_by: str = "updated_at",
    direction: str = "desc",
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    return await _render_recommendation_list(
        request=request,
        user=user,
        author=author,
        repository=repository,
        q=q,
        status_filter=status_filter,
        sort_by=sort_by,
        direction=direction,
    )


@router.get("/recommendations/new", response_class=HTMLResponse)
async def recommendation_create_page(
    request: Request,
    embedded: int = 0,
    next: str = "/author/recommendations",
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    if embedded != 1:
        return RedirectResponse(url="/author/recommendations?modal=new", status_code=status.HTTP_303_SEE_OTHER)
    author = await _get_author_or_403(repository, user)
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        repository=repository,
        recommendation=None,
        error=None,
        form_values=_build_recommendation_prefill_form_values(request=request, author=author),
        embedded=True,
        next_path=next,
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
    resolved_status = _resolve_status_value(
        status_value=str(form.get("status", "") or ""),
        workflow_action=str(form.get("workflow_action", "") or ""),
    )
    inline_mode = str(form.get("inline_mode", "") or "") == "1"
    strategy_id = str(form.get("strategy_id", "") or "")
    if not strategy_id.strip():
        return await _render_recommendation_create_error(
            request=request,
            user=user,
            author=author,
            repository=repository,
            form=form,
            resolved_status=resolved_status,
            leg_rows=leg_rows,
            inline_mode=inline_mode,
            error_text="Выберите стратегию автора.",
        )
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        data = build_recommendation_form_data(
            strategy_id=strategy_id,
            kind_value=str(form.get("kind", "new_idea") or "new_idea"),
            status_value=resolved_status,
            title=str(form.get("title", "") or ""),
            summary=str(form.get("summary", "") or ""),
            thesis=str(form.get("thesis", "") or ""),
            market_context=str(form.get("market_context", "") or ""),
            author_requires_moderation=author.requires_moderation,
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
        return await _render_recommendation_create_error(
            request=request,
            user=user,
            author=author,
            repository=repository,
            form=form,
            resolved_status=resolved_status,
            leg_rows=leg_rows,
            inline_mode=inline_mode,
            error_text=str(exc),
        )
    if data.status == RecommendationStatus.PUBLISHED:
        await _deliver_author_publish_notifications(
            repository=repository,
            author=author,
            recommendation_id=recommendation.id,
            trigger="author_publish_create",
        )
    next_path = _safe_author_next_path(str(form.get("next_path", "") or ""))
    if inline_mode:
        return RedirectResponse(
            url=next_path or "/author/recommendations",
            status_code=status.HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(url=next_path or f"/author/recommendations/{recommendation.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


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
    resolved_status = _resolve_status_value(
        status_value=str(form.get("status", "") or ""),
        workflow_action=str(form.get("workflow_action", "") or ""),
    )
    was_published = recommendation.status == RecommendationStatus.PUBLISHED
    remove_attachment_ids = [str(item) for item in form.getlist("remove_attachment_ids")]
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        data = build_recommendation_form_data(
            strategy_id=str(form.get("strategy_id", "") or ""),
            kind_value=str(form.get("kind", "") or ""),
            status_value=resolved_status,
            title=str(form.get("title", "") or ""),
            summary=str(form.get("summary", "") or ""),
            thesis=str(form.get("thesis", "") or ""),
            market_context=str(form.get("market_context", "") or ""),
            author_requires_moderation=author.requires_moderation,
            scheduled_for=str(form.get("scheduled_for", "") or ""),
            allowed_strategy_ids={item.id for item in strategies},
            allowed_instrument_ids={item.id for item in instruments},
            leg_rows=leg_rows,
            attachments=uploads,
        )
        await remove_recommendation_attachments(repository, recommendation, remove_attachment_ids)
        await update_author_recommendation(
            repository,
            recommendation,
            data,
            uploaded_by_user_id=user.id,
        )
    except ValueError as exc:
        feedback = _build_recommendation_form_feedback(str(exc), leg_rows)
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            repository=repository,
            recommendation=recommendation,
            error=feedback["error"],
            form_values={
                "strategy_id": str(form.get("strategy_id", "") or ""),
                "kind": str(form.get("kind", "") or ""),
                "status": resolved_status,
                "title": str(form.get("title", "") or ""),
                "summary": str(form.get("summary", "") or ""),
                "thesis": str(form.get("thesis", "") or ""),
                "market_context": str(form.get("market_context", "") or ""),
                "requires_moderation": author.requires_moderation,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "legs": leg_form_values_from_rows(leg_rows),
            },
            field_errors=feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            embedded=str(form.get("embedded", "") or "") == "1",
            next_path=str(form.get("next_path", "") or ""),
        )
    if data.status == RecommendationStatus.PUBLISHED:
        await _deliver_author_publish_notifications(
            repository=repository,
            author=author,
            recommendation_id=recommendation.id,
            trigger="author_publish_update",
            was_published=was_published,
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
    field_errors: dict[str, str] | None = None,
    status_code: int = status.HTTP_200_OK,
    embedded: bool = False,
    next_path: str = "",
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
            "field_errors": field_errors or {},
            "form_values": effective_form_values,
            "next_leg_index": _next_leg_index(effective_form_values),
            "embedded": embedded,
            "next_path": _safe_author_next_path(next_path) or "/author/recommendations",
        },
        status_code=status_code,
    )


async def _render_recommendation_list(
    *,
    request: Request,
    user: User,
    author: AuthorProfile,
    repository: AuthorRepository,
    q: str = "",
    status_filter: str = "all",
    sort_by: str = "updated_at",
    direction: str = "desc",
    inline_error: str | None = None,
    inline_form_values: dict[str, str] | None = None,
    inline_field_errors: dict[str, str] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    recommendations = await list_author_recommendations(repository, author)
    recommendations = _filter_author_recommendations(recommendations, q=q, status_filter=status_filter)
    recommendations = _sort_author_recommendations(recommendations, sort_by=sort_by, direction=direction)
    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    current_list_path = _author_recommendations_list_path(
        q=q,
        status_filter=status_filter,
        sort_by=sort_by,
        direction=direction,
    )
    return templates.TemplateResponse(
        request,
        "author/recommendations_list.html",
        {
            "title": "Рекомендации автора",
            "user": user,
            "author": author,
            "recommendations": recommendations,
            "strategies": strategies,
            "instruments": instruments,
            "instrument_items": [_instrument_payload(item) for item in instruments],
            "q": q,
            "status_filter": status_filter,
            "sort_by": sort_by,
            "direction": direction,
            "recommendation_modal_url": _recommendation_modal_url(next_path=current_list_path),
            "inline_next_path": current_list_path,
            "inline_error": inline_error,
            "inline_field_errors": inline_field_errors or {},
            "inline_form_values": _normalize_inline_recommendation_form_values(inline_form_values, instruments),
        },
        status_code=status_code,
    )


async def _render_recommendation_create_error(
    *,
    request: Request,
    user: User,
    author: AuthorProfile,
    repository: AuthorRepository,
    form,
    resolved_status: str,
    leg_rows: list[dict[str, str]],
    inline_mode: bool,
    error_text: str,
) -> Response:
    if inline_mode:
        inline_feedback = _build_inline_recommendation_feedback(error_text, leg_rows)
        return await _render_recommendation_list(
            request=request,
            user=user,
            author=author,
            repository=repository,
            q=str(form.get("q", "") or ""),
            status_filter=str(form.get("status_filter", "all") or "all"),
            sort_by=str(form.get("sort_by", "updated_at") or "updated_at"),
            direction=str(form.get("direction", "desc") or "desc"),
            inline_error=inline_feedback["error"],
            inline_form_values=_build_inline_recommendation_form_values(form),
            inline_field_errors=inline_feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    feedback = _build_recommendation_form_feedback(error_text, leg_rows)
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        repository=repository,
        recommendation=None,
        error=feedback["error"],
        form_values={
            "strategy_id": str(form.get("strategy_id", "") or ""),
            "kind": str(form.get("kind", "new_idea") or "new_idea"),
            "status": resolved_status,
            "title": str(form.get("title", "") or ""),
            "summary": str(form.get("summary", "") or ""),
            "thesis": str(form.get("thesis", "") or ""),
            "market_context": str(form.get("market_context", "") or ""),
            "requires_moderation": author.requires_moderation,
            "scheduled_for": str(form.get("scheduled_for", "") or ""),
            "legs": leg_form_values_from_rows(leg_rows),
        },
        field_errors=feedback["field_errors"],
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        embedded=str(form.get("embedded", "") or "") == "1",
        next_path=str(form.get("next_path", "") or ""),
    )


async def _deliver_author_publish_notifications(
    *,
    repository: AuthorRepository,
    author: AuthorProfile,
    recommendation_id: str,
    trigger: str,
    was_published: bool = False,
) -> None:
    bot = None
    try:
        recommendation = await get_author_recommendation(repository, author, recommendation_id)
        if recommendation is None or recommendation.status != RecommendationStatus.PUBLISHED or was_published:
            return

        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        if isinstance(repository, FileAuthorRepository):
            await deliver_recommendation_notifications_file(
                repository.graph,
                repository.store,
                recommendation,
                bot,
                trigger=trigger,
            )
            return
        if isinstance(repository, SqlAlchemyAuthorRepository):
            await deliver_recommendation_notifications(
                repository.session,
                recommendation,
                bot,
                trigger=trigger,
            )
            return
        logger.warning(
            "Skipping immediate notification delivery for recommendation %s: unsupported repository %s",
            recommendation_id,
            type(repository).__name__,
        )
    except Exception:
        logger.exception("Immediate notification delivery failed for recommendation %s", recommendation_id)
    finally:
        if bot is not None:
            await bot.session.close()


async def _get_author_or_403(repository: AuthorRepository, user: User) -> AuthorProfile:
    author = user.author_profile or await get_author_by_user(repository, user)
    if author is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Author profile is not configured")
    return author


def _resolve_status_value(*, status_value: str, workflow_action: str) -> str:
    mapping = {
        "save_draft": "draft",
        "send_to_review": "review",
        "schedule": "scheduled",
        "publish_now": "published",
        "close_idea": "closed",
        "cancel_idea": "cancelled",
    }
    normalized_action = workflow_action.strip()
    if not normalized_action:
        return status_value
    return mapping.get(normalized_action, status_value)


def _next_leg_index(form_values: dict[str, object]) -> int:
    legs = form_values.get("legs", [])
    if not isinstance(legs, list) or not legs:
        return 1
    indexes: list[int] = []
    for item in legs:
        if not isinstance(item, dict):
            continue
        try:
            indexes.append(int(str(item.get("row_id", "0"))))
        except ValueError:
            continue
    return (max(indexes) + 1) if indexes else len(legs)


def _build_recommendation_form_feedback(error_text: str, leg_rows: list[dict[str, str]]) -> dict[str, object]:
    first_row_id = str(leg_rows[0].get("row_id", "0")) if leg_rows else "0"
    field_errors = _build_leg_field_errors(
        error_text,
        row_id=first_row_id,
        instrument_error="Выберите инструмент из списка",
    )
    if error_text == "Выберите стратегию автора.":
        field_errors["strategy_id"] = "Выберите стратегию автора"
    return {"error": _friendly_recommendation_error_message(error_text), "field_errors": field_errors}


def _build_inline_recommendation_feedback(error_text: str, leg_rows: list[dict[str, str]]) -> dict[str, object]:
    first_row_id = str(leg_rows[0].get("row_id", "1")) if leg_rows else "1"
    field_errors = _build_leg_field_errors(
        error_text,
        row_id=first_row_id,
        instrument_error="Выберите бумагу из подсказок",
    )
    if error_text == "Выберите стратегию автора.":
        field_errors["strategy_id"] = "Выберите стратегию автора"
    return {"error": _friendly_recommendation_error_message(error_text), "field_errors": field_errors}


def _build_leg_field_errors(error_text: str, *, row_id: str, instrument_error: str) -> dict[str, str]:
    field_prefix = f"leg_{row_id}_"
    if error_text.startswith("Leg 1: выберите допустимый инструмент."):
        return {f"{field_prefix}instrument_id": instrument_error}
    if error_text.startswith("Leg 1: выберите направление сделки."):
        return {f"{field_prefix}side": "Выберите направление сделки"}
    if error_text.startswith("Leg 1: некорректный entry_from."):
        return {f"{field_prefix}entry_from": "Укажите корректную цену входа"}
    if error_text.startswith("Leg 1: некорректный entry_to."):
        return {f"{field_prefix}entry_to": "Укажите корректную цену входа"}
    if error_text.startswith("Leg 1: entry_to не может быть меньше entry_from."):
        return {f"{field_prefix}entry_to": "Значение не может быть меньше цены «от»"}
    if error_text.startswith("Leg 1: некорректный stop_loss."):
        return {f"{field_prefix}stop_loss": "Укажите корректный стоп"}
    if error_text.startswith("Leg 1: некорректный take_profit_1."):
        return {f"{field_prefix}take_profit_1": "Укажите корректный TP1"}
    if error_text.startswith("Leg 1: некорректный take_profit_2."):
        return {f"{field_prefix}take_profit_2": "Укажите корректный TP2"}
    if error_text.startswith("Leg 1: некорректный take_profit_3."):
        return {f"{field_prefix}take_profit_3": "Укажите корректный TP3"}
    return {}


def _friendly_recommendation_error_message(error_text: str) -> str:
    if error_text.startswith("Leg 1: выберите допустимый инструмент."):
        return "Выберите инструмент для первой бумаги."
    if error_text.startswith("Leg 1: выберите направление сделки."):
        return "Укажите направление для первой бумаги."
    if error_text.startswith("Leg 1: некорректный entry_from."):
        return "Проверьте цену входа для первой бумаги."
    if error_text.startswith("Leg 1: некорректный entry_to."):
        return "Проверьте диапазон цены входа для первой бумаги."
    if error_text.startswith("Leg 1: entry_to не может быть меньше entry_from."):
        return "Цена входа «до» должна быть не ниже цены «от»."
    if error_text.startswith("Leg 1: некорректный stop_loss."):
        return "Проверьте стоп для первой бумаги."
    if error_text.startswith("Leg 1: некорректный take_profit_1."):
        return "Проверьте TP1 для первой бумаги."
    if error_text.startswith("Leg 1: некорректный take_profit_2."):
        return "Проверьте TP2 для первой бумаги."
    if error_text.startswith("Leg 1: некорректный take_profit_3."):
        return "Проверьте TP3 для первой бумаги."
    if error_text == "Для scheduled нужен planned datetime.":
        return "Укажите дату и время для запланированной публикации."
    return error_text


def _instrument_payload(instrument) -> dict[str, str]:
    return {
        "id": instrument.id,
        "ticker": instrument.ticker,
        "name": instrument.name,
        "board": instrument.board,
        "currency": instrument.currency,
    }


def _watchlist_candidate_payload(candidate: WatchlistCandidate) -> dict[str, str]:
    return {
        "id": candidate.id,
        "ticker": candidate.ticker,
        "name": candidate.name,
        "board": candidate.board,
        "source": candidate.source,
    }


def _safe_author_next_path(next_path: str) -> str:
    normalized = next_path.strip()
    if not normalized.startswith("/author/"):
        return ""
    return normalized


def _author_recommendations_list_path(*, q: str, status_filter: str, sort_by: str, direction: str) -> str:
    params: list[tuple[str, str]] = []
    if q.strip():
        params.append(("q", q.strip()))
    if status_filter != "all":
        params.append(("status_filter", status_filter))
    if sort_by != "updated_at":
        params.append(("sort_by", sort_by))
    if direction != "desc":
        params.append(("direction", direction))
    if not params:
        return "/author/recommendations"
    return f"/author/recommendations?{urlencode(params)}"


def _recommendation_modal_url(*, next_path: str) -> str:
    return f"/author/recommendations/new?{urlencode({'embedded': '1', 'next': next_path})}"


def _build_recommendation_prefill_form_values(*, request: Request, author: AuthorProfile) -> dict[str, object]:
    form_values = recommendation_form_values(None)
    form_values.update(
        {
            "strategy_id": str(request.query_params.get("strategy_id", "") or ""),
            "kind": str(request.query_params.get("kind", form_values["kind"]) or form_values["kind"]),
            "status": str(request.query_params.get("status", form_values["status"]) or form_values["status"]),
            "title": str(request.query_params.get("title", "") or ""),
            "summary": str(request.query_params.get("summary", "") or ""),
            "thesis": str(request.query_params.get("thesis", "") or ""),
            "market_context": str(request.query_params.get("market_context", "") or ""),
            "requires_moderation": author.requires_moderation,
            "scheduled_for": str(request.query_params.get("scheduled_for", "") or ""),
            "legs": leg_form_values_from_rows(build_leg_rows_from_form(request.query_params)),
        }
    )
    return form_values


def _normalize_inline_recommendation_form_values(
    inline_form_values: dict[str, str] | None,
    instruments,
) -> dict[str, str]:
    values = {
        "strategy_id": "",
        "kind": "new_idea",
        "status": "draft",
        "title": "",
        "instrument_query": "",
        "leg_1_instrument_id": "",
        "leg_1_side": "",
        "leg_1_entry_from": "",
        "leg_1_entry_to": "",
        "leg_1_stop_loss": "",
        "leg_1_take_profit_1": "",
        "leg_1_take_profit_2": "",
        "leg_1_take_profit_3": "",
        "leg_1_time_horizon": "",
        "leg_1_note": "",
    }
    if inline_form_values:
        values.update({key: str(value or "") for key, value in inline_form_values.items() if key in values})
    if not values["instrument_query"] and values["leg_1_instrument_id"]:
        selected = next((item for item in instruments if item.id == values["leg_1_instrument_id"]), None)
        if selected is not None:
            values["instrument_query"] = selected.ticker
    return values


def _build_inline_recommendation_form_values(form) -> dict[str, str]:
    return {
        "strategy_id": str(form.get("strategy_id", "") or ""),
        "kind": str(form.get("kind", "new_idea") or "new_idea"),
        "status": str(form.get("status", "draft") or "draft"),
        "title": str(form.get("title", "") or ""),
        "instrument_query": str(form.get("instrument_query", "") or ""),
        "leg_1_instrument_id": str(form.get("leg_1_instrument_id", "") or ""),
        "leg_1_side": str(form.get("leg_1_side", "") or ""),
        "leg_1_entry_from": str(form.get("leg_1_entry_from", "") or ""),
        "leg_1_entry_to": str(form.get("leg_1_entry_to", "") or ""),
        "leg_1_stop_loss": str(form.get("leg_1_stop_loss", "") or ""),
        "leg_1_take_profit_1": str(form.get("leg_1_take_profit_1", "") or ""),
        "leg_1_take_profit_2": str(form.get("leg_1_take_profit_2", "") or ""),
        "leg_1_take_profit_3": str(form.get("leg_1_take_profit_3", "") or ""),
        "leg_1_time_horizon": str(form.get("leg_1_time_horizon", "") or ""),
        "leg_1_note": str(form.get("leg_1_note", "") or ""),
    }


def _filter_author_recommendations(recommendations, *, q: str, status_filter: str):
    normalized = q.strip().lower()
    items = recommendations
    if status_filter != "all":
        items = [item for item in items if item.status.value == status_filter]
    if not normalized:
        return items
    return [
        item
        for item in items
        if normalized in " ".join(
            part.lower()
            for part in [
                item.title or "",
                item.summary or "",
                item.strategy.title if item.strategy is not None else "",
                item.status.value,
                item.kind.value,
                " ".join((leg.instrument.ticker if leg.instrument is not None else "") for leg in item.legs),
            ]
            if part
        )
    ]


def _sort_author_recommendations(recommendations, *, sort_by: str, direction: str):
    reverse = direction == "desc"
    if sort_by == "title":
        key = lambda item: (item.title or item.strategy.title if item.strategy is not None else "").lower()
    elif sort_by == "strategy":
        key = lambda item: (item.strategy.title if item.strategy is not None else "").lower()
    elif sort_by == "status":
        key = lambda item: item.status.value
    else:
        key = lambda item: (item.updated_at, item.created_at)
    return sorted(recommendations, key=key, reverse=reverse)


def _filter_author_strategies(strategies, *, q: str):
    normalized = q.strip().lower()
    if not normalized:
        return strategies
    return [
        item
        for item in strategies
        if normalized in " ".join(
            part.lower()
            for part in [item.title, item.slug, item.short_description or "", item.status.value, item.risk_level.value]
            if part
        )
    ]


def _sort_author_strategies(strategies, *, sort_by: str, direction: str):
    reverse = direction == "desc"
    if sort_by == "status":
        key = lambda item: item.status.value
    elif sort_by == "risk":
        key = lambda item: item.risk_level.value
    else:
        key = lambda item: item.title.lower()
    return sorted(strategies, key=key, reverse=reverse)
