from __future__ import annotations

import logging
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from pitchcopytrade.api.deps.auth import require_author
from pitchcopytrade.api.deps.repositories import get_author_repository
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.db.models.enums import MessageStatus
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.repositories.author import FileAuthorRepository, SqlAlchemyAuthorRepository
from pitchcopytrade.services.author import (
    WatchlistCandidate,
    add_author_watchlist_instrument,
    build_author_strategy_form_data,
    build_recommendation_form_data,
    create_author_recommendation,
    create_author_strategy,
    get_author_by_user,
    get_author_recommendation,
    get_author_strategy,
    get_author_workspace_stats,
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
from pitchcopytrade.services.notifications import deliver_message_notifications, deliver_message_notifications_file
from pitchcopytrade.services.instruments import build_instrument_payloads, get_or_import_instrument_by_symbol
from pitchcopytrade.web.templates import label_message_status, templates
from pitchcopytrade.api.routes._grid_serializers import (
    serialize_recommendations,
    serialize_author_strategies,
)


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
    combined_instruments = _unique_instruments_by_id([*watchlist, *instruments])
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        len(combined_instruments),
        get_settings().instrument_quotes.provider_enabled,
    )
    instrument_items = await build_instrument_payloads(combined_instruments, allow_live_fetch=False)
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        instrument_items=instrument_items,
        composer_default_open=False,
    )
    instrument_items_by_id = _index_instrument_items(instrument_items)
    watchlist_items = [instrument_items_by_id[item.id] for item in watchlist if item.id in instrument_items_by_id]
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
            "watchlist_items": watchlist_items,
            "strategies_all": strategies,
            **composer_context,
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
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        composer_default_open=False,
    )
    return templates.TemplateResponse(
        request,
        "author/strategies_list.html",
        {
            "title": "Стратегии автора",
            "user": user,
            "author": author,
            "strategies": strategies,
            "strategies_json": serialize_author_strategies(strategies),
            "q": q,
            "sort_by": sort_by,
            "direction": direction,
            **composer_context,
        },
    )


@router.get("/strategies/new", response_class=HTMLResponse)
async def author_strategy_create_page(
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        composer_default_open=False,
    )
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
            **composer_context,
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
    instruments = await list_active_instruments(repository)
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        composer_default_open=False,
    )
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
                **composer_context,
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
    strategies = await list_author_strategies(repository, author)
    strategy = await get_author_strategy(repository, author, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    instruments = await list_active_instruments(repository)
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        composer_default_open=False,
    )
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
            **composer_context,
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
    instruments = await list_active_instruments(repository)
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        composer_default_open=False,
    )
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
                **composer_context,
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
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        1,
        get_settings().instrument_quotes.provider_enabled,
    )
    added_payload = (await build_instrument_payloads([instrument], allow_live_fetch=False))[0]
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        len(watchlist),
        get_settings().instrument_quotes.provider_enabled,
    )
    watchlist_payload = await build_instrument_payloads(watchlist, allow_live_fetch=False)
    return JSONResponse(
        {
            "added": added_payload,
            "watchlist": watchlist_payload,
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
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        len(watchlist),
        get_settings().instrument_quotes.provider_enabled,
    )
    watchlist_payload = await build_instrument_payloads(watchlist, allow_live_fetch=False)
    return JSONResponse(
        {
            "removed_id": instrument_id,
            "watchlist": watchlist_payload,
        }
    )


@router.get("/messages", response_class=HTMLResponse)
async def recommendation_list_page(
    request: Request,
    q: str = "",
    status_filter: str = "all",
    sort_by: str = "updated_at",
    direction: str = "desc",
    date_from: str = "",
    date_to: str = "",
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
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/messages/new", response_class=HTMLResponse)
async def recommendation_create_page(
    request: Request,
    embedded: int = 0,
    next: str = "/author/messages",
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
        form_values=_build_recommendation_prefill_form_values(request=request, author=author),
        embedded=False,
        next_path=next,
    )


@router.post("/messages", response_class=HTMLResponse)
async def recommendation_create_submit(
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    form = await request.form()
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
            inline_mode=inline_mode,
            error_text="Выберите стратегию автора.",
        )
    selected_instrument_id = str(form.get("structured_instrument_id", "") or "").strip()
    selected_instrument = next((item for item in instruments if item.id == selected_instrument_id), None)
    structured_instrument_query = str(form.get("structured_instrument_query", "") or "").strip()
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        selected_instrument, selected_instrument_id = await _resolve_structured_instrument_selection(
            repository,
            instruments,
            selected_instrument_id=selected_instrument_id,
            structured_instrument_query=structured_instrument_query,
        )
        remaining_documents: list[dict[str, object]] = []
        message_type_value = _derive_message_type_value(
            text_value=str(form.get("message_text", "") or ""),
            documents=uploads,
            structured_instrument_id=selected_instrument_id,
            structured_side_value=str(form.get("structured_side", "") or ""),
            structured_price_value=str(form.get("structured_price", "") or ""),
            structured_quantity_value=str(form.get("structured_quantity", "") or ""),
            structured_tp_value=str(form.get("structured_tp", "") or ""),
            structured_sl_value=str(form.get("structured_sl", "") or ""),
            structured_note_value=str(form.get("structured_note", "") or ""),
        )
    except ValueError as exc:
        return await _render_recommendation_create_error(
            request=request,
            user=user,
            author=author,
            repository=repository,
            form=form,
            resolved_status=resolved_status,
            inline_mode=inline_mode,
            error_text=str(exc),
        )
    try:
        data = build_recommendation_form_data(
            strategy_id=strategy_id,
            kind_value=str(form.get("kind", "new_idea") or "new_idea"),
            status_value=resolved_status,
            title=str(form.get("title", "") or ""),
            type_value=message_type_value,
            message_mode=message_type_value,
            message_text=str(form.get("message_text", "") or ""),
            document_caption=str(form.get("document_caption", "") or ""),
            structured_instrument_id=selected_instrument_id,
            structured_side_value=str(form.get("structured_side", "") or ""),
            structured_price=str(form.get("structured_price", "") or ""),
            structured_quantity=str(form.get("structured_quantity", "") or ""),
            structured_tp=str(form.get("structured_tp", "") or ""),
            structured_sl=str(form.get("structured_sl", "") or ""),
            structured_note=str(form.get("structured_note", "") or ""),
            author_requires_moderation=author.requires_moderation,
            scheduled_for=str(form.get("scheduled_for", "") or ""),
            allowed_strategy_ids={item.id for item in strategies},
            allowed_instrument_ids={item.id for item in instruments} | ({selected_instrument.id} if selected_instrument is not None else set()),
            selected_instrument=selected_instrument,
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
            inline_mode=inline_mode,
            error_text=str(exc),
        )
    if getattr(data.status, "value", data.status) == MessageStatus.PUBLISHED.value:
        await _deliver_author_publish_notifications(
            repository=repository,
            author=author,
            recommendation_id=recommendation.id,
            trigger="author_publish_create",
        )
    next_path = _safe_author_next_path(str(form.get("next_path", "") or ""))
    return RedirectResponse(url=next_path or f"/author/messages/{recommendation.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/messages/{recommendation_id}/edit", response_class=HTMLResponse)
async def recommendation_edit_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return await _render_recommendation_form(
        request=request,
        user=user,
        author=author,
        repository=repository,
        recommendation=recommendation,
        error=None,
        form_values=None,
    )


@router.get("/messages/{recommendation_id}/preview", response_class=HTMLResponse)
async def recommendation_preview_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return templates.TemplateResponse(
        request,
        "app/message_detail.html",
        {
            "title": recommendation.title or recommendation.strategy.title,
            "user": user,
            "recommendation": recommendation,
            "preview_mode": True,
            "attachment_download_enabled": False,
        },
    )


@router.post("/messages/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_edit_submit(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> Response:
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    form = await request.form()
    resolved_status = _resolve_status_value(
        status_value=str(form.get("status", "") or ""),
        workflow_action=str(form.get("workflow_action", "") or ""),
    )
    selected_instrument_id = str(form.get("structured_instrument_id", "") or "").strip()
    selected_instrument = next((item for item in instruments if item.id == selected_instrument_id), None)
    structured_instrument_query = str(form.get("structured_instrument_query", "") or "").strip()
    remove_attachment_ids = [str(item) for item in form.getlist("remove_attachment_ids")]
    current_documents = list(recommendation.documents or [])
    remaining_documents = [item for item in current_documents if str(item.get("id")) not in remove_attachment_ids]
    message_type_value = str(form.get("message_type", "") or form.get("message_mode", "") or "mixed")
    strategy_id = str(form.get("strategy_id", "") or "")
    if not strategy_id.strip():
        feedback = _build_recommendation_form_feedback("Выберите стратегию автора.")
        return await _render_recommendation_form(
            request=request,
            user=user,
            author=author,
            repository=repository,
            recommendation=recommendation,
            error=feedback["error"],
            form_values={
                "strategy_id": "",
                "kind": str(form.get("kind", "") or ""),
                "status": resolved_status,
                "title": str(form.get("title", "") or ""),
                "message_type": message_type_value,
                "message_mode": message_type_value,
                "message_text": str(form.get("message_text", "") or ""),
                "document_caption": str(form.get("document_caption", "") or ""),
                "structured_instrument_id": selected_instrument_id,
                "structured_instrument_query": structured_instrument_query,
                "structured_instrument_ticker": selected_instrument.ticker if selected_instrument is not None else "",
                "structured_instrument_name": selected_instrument.name if selected_instrument is not None else "",
                "structured_amount": str(form.get("structured_amount", "") or ""),
                "structured_side": str(form.get("structured_side", "") or ""),
                "structured_price": str(form.get("structured_price", "") or ""),
                "structured_quantity": str(form.get("structured_quantity", "") or ""),
                "structured_tp": str(form.get("structured_tp", "") or ""),
                "structured_sl": str(form.get("structured_sl", "") or ""),
                "structured_note": str(form.get("structured_note", "") or ""),
                "requires_moderation": author.requires_moderation,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "documents": remaining_documents,
            },
            field_errors=feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            embedded=str(form.get("embedded", "") or "") == "1",
            next_path=str(form.get("next_path", "") or ""),
        )
    was_published = getattr(recommendation.status, "value", recommendation.status) == MessageStatus.PUBLISHED.value
    try:
        uploads = await normalize_attachment_uploads(form.getlist("attachment_files"))
        selected_instrument, selected_instrument_id = await _resolve_structured_instrument_selection(
            repository,
            instruments,
            selected_instrument_id=selected_instrument_id,
            structured_instrument_query=structured_instrument_query,
        )
        message_type_value = _derive_message_type_value(
            text_value=str(form.get("message_text", "") or ""),
            documents=remaining_documents + uploads,
            structured_instrument_id=selected_instrument_id,
            structured_side_value=str(form.get("structured_side", "") or ""),
            structured_price_value=str(form.get("structured_price", "") or ""),
            structured_quantity_value=str(form.get("structured_quantity", "") or ""),
            structured_tp_value=str(form.get("structured_tp", "") or ""),
            structured_sl_value=str(form.get("structured_sl", "") or ""),
            structured_note_value=str(form.get("structured_note", "") or ""),
        )
    except ValueError as exc:
        feedback = _build_recommendation_form_feedback(str(exc))
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
                "message_type": message_type_value,
                "message_mode": message_type_value,
                "message_text": str(form.get("message_text", "") or ""),
                "document_caption": str(form.get("document_caption", "") or ""),
                "structured_instrument_id": selected_instrument_id,
                "structured_instrument_query": structured_instrument_query,
                "structured_instrument_ticker": selected_instrument.ticker if selected_instrument is not None else "",
                "structured_instrument_name": selected_instrument.name if selected_instrument is not None else "",
                "structured_amount": str(form.get("structured_amount", "") or ""),
                "structured_side": str(form.get("structured_side", "") or ""),
                "structured_price": str(form.get("structured_price", "") or ""),
                "structured_quantity": str(form.get("structured_quantity", "") or ""),
                "structured_tp": str(form.get("structured_tp", "") or ""),
                "structured_sl": str(form.get("structured_sl", "") or ""),
                "structured_note": str(form.get("structured_note", "") or ""),
                "requires_moderation": author.requires_moderation,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "documents": remaining_documents,
            },
            field_errors=feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            embedded=str(form.get("embedded", "") or "") == "1",
            next_path=str(form.get("next_path", "") or ""),
        )
    try:
        data = build_recommendation_form_data(
            strategy_id=str(form.get("strategy_id", "") or ""),
            kind_value=str(form.get("kind", "") or ""),
            status_value=resolved_status,
            title=str(form.get("title", "") or ""),
            type_value=message_type_value,
            message_mode=message_type_value,
            message_text=str(form.get("message_text", "") or ""),
            document_caption=str(form.get("document_caption", "") or ""),
            structured_instrument_id=selected_instrument_id,
            structured_side_value=str(form.get("structured_side", "") or ""),
            structured_price=str(form.get("structured_price", "") or ""),
            structured_quantity=str(form.get("structured_quantity", "") or ""),
            structured_tp=str(form.get("structured_tp", "") or ""),
            structured_sl=str(form.get("structured_sl", "") or ""),
            structured_note=str(form.get("structured_note", "") or ""),
            author_requires_moderation=author.requires_moderation,
            scheduled_for=str(form.get("scheduled_for", "") or ""),
            allowed_strategy_ids={item.id for item in strategies},
            allowed_instrument_ids={item.id for item in instruments} | ({selected_instrument.id} if selected_instrument is not None else set()),
            selected_instrument=selected_instrument,
            documents=remaining_documents,
            attachments=uploads,
        )
        await update_author_recommendation(
            repository,
            author,
            recommendation,
            data,
            uploaded_by_user_id=user.id,
        )
        if remove_attachment_ids:
            await remove_recommendation_attachments(
                repository,
                Message(documents=current_documents),
                remove_attachment_ids,
            )
    except ValueError as exc:
        feedback = _build_recommendation_form_feedback(str(exc))
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
                "message_type": message_type_value,
                "message_mode": message_type_value,
                "message_text": str(form.get("message_text", "") or ""),
                "document_caption": str(form.get("document_caption", "") or ""),
                "structured_instrument_id": selected_instrument_id,
                "structured_instrument_query": str(form.get("structured_instrument_query", "") or ""),
                "structured_instrument_ticker": selected_instrument.ticker if selected_instrument is not None else "",
                "structured_instrument_name": selected_instrument.name if selected_instrument is not None else "",
                "structured_amount": str(form.get("structured_amount", "") or ""),
                "structured_side": str(form.get("structured_side", "") or ""),
                "structured_price": str(form.get("structured_price", "") or ""),
                "structured_quantity": str(form.get("structured_quantity", "") or ""),
                "structured_tp": str(form.get("structured_tp", "") or ""),
                "structured_sl": str(form.get("structured_sl", "") or ""),
                "structured_note": str(form.get("structured_note", "") or ""),
                "requires_moderation": author.requires_moderation,
                "scheduled_for": str(form.get("scheduled_for", "") or ""),
                "documents": remaining_documents,
            },
            field_errors=feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            embedded=str(form.get("embedded", "") or "") == "1",
            next_path=str(form.get("next_path", "") or ""),
        )
    if getattr(data.status, "value", data.status) == MessageStatus.PUBLISHED.value:
        await _deliver_author_publish_notifications(
            repository=repository,
            author=author,
            recommendation_id=recommendation.id,
            trigger="author_publish_update",
            was_published=was_published,
        )

    return RedirectResponse(
            url=f"/author/messages/{recommendation.id}/edit",
            status_code=status.HTTP_303_SEE_OTHER,
        )


@router.patch("/messages/{recommendation_id}/inline")
async def inline_update_recommendation(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_author),
    repository: AuthorRepository = Depends(get_author_repository),
) -> JSONResponse:
    """Update a single field of a recommendation inline."""
    author = await _get_author_or_403(repository, user)
    recommendation = await get_author_recommendation(repository, author, recommendation_id)
    if recommendation is None:
        return JSONResponse({"error": "not_found"}, status_code=404)

    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    field = body.get("field", "")
    value = body.get("value", "")

    # Map field names to canonical message attributes
    try:
        if field == "title":
            recommendation.title = str(value).strip()
        elif field in {"instrument", "ticker", "name", "side", "price", "quantity", "amount", "board", "currency", "lot", "from", "to", "stop", "targets", "period", "note", "status", "opened", "closed", "result"}:
            deals = list(recommendation.deals or [])
            if not deals:
                deals = [{}]
            deal = dict(deals[0])
            deal[field] = value
            deals[0] = deal
            recommendation.deals = deals
        elif field == "status":
            status_value = str(value).lower()
            if status_value in ["draft", "review", "published", "archived", "scheduled", "approved", "failed"]:
                recommendation.status = status_value
            else:
                return JSONResponse({"error": "invalid_status"}, status_code=400)
        else:
            return JSONResponse({"error": "unknown_field"}, status_code=400)

        # Commit the changes
        await repository.commit()
        await repository.refresh(recommendation)
    except Exception as exc:
        return JSONResponse({"error": str(exc)}, status_code=500)

    return JSONResponse({"ok": True, "field": field, "value": value})


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
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        len(instruments),
        get_settings().instrument_quotes.provider_enabled,
    )
    try:
        history_messages = await list_author_recommendations(repository, author)
    except AttributeError:
        history_messages = [recommendation] if recommendation is not None else []
    composer_context = await _get_composer_context(
        repository,
        author,
        recommendation=recommendation,
        form_values=effective_form_values,
        strategies=strategies,
        instruments=instruments,
        history_messages=history_messages,
        composer_default_open=True,
    )
    return templates.TemplateResponse(
        request,
        "author/message_form.html",
        {
            "title": "Редактор сообщения" if recommendation else "Новое сообщение",
            "user": user,
            "author": author,
            "recommendation": recommendation,
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
            "recommendation_message_modes": ["mixed", "text", "document", "deal"],
            "error": error,
            "field_errors": field_errors or {},
            "next_path": _safe_author_next_path(next_path) or "/author/messages",
            "embedded": embedded,
            **composer_context,
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
    date_from: str = "",
    date_to: str = "",
    inline_error: str | None = None,
    inline_form_values: dict[str, str] | None = None,
    inline_field_errors: dict[str, str] | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    from datetime import datetime
    recommendations = await list_author_recommendations(repository, author)
    recommendations = _filter_author_recommendations(recommendations, q=q, status_filter=status_filter)
    # Date filtering
    if date_from:
        try:
            df = datetime.fromisoformat(date_from).date()
            recommendations = [r for r in recommendations if r.updated_at and r.updated_at.date() >= df]
        except (ValueError, AttributeError):
            pass
    if date_to:
        try:
            from datetime import timedelta
            dt = datetime.fromisoformat(date_to).date() + timedelta(days=1)
            recommendations = [r for r in recommendations if r.updated_at and r.updated_at.date() < dt]
        except (ValueError, AttributeError):
            pass
    recommendations = _sort_author_recommendations(recommendations, sort_by=sort_by, direction=direction)
    strategies = await list_author_strategies(repository, author)
    instruments = await list_active_instruments(repository)
    logger.info(
        "Building instrument payloads for %d instruments, provider_enabled=%s",
        len(instruments),
        get_settings().instrument_quotes.provider_enabled,
    )
    composer_context = await _get_composer_context(
        repository,
        author,
        strategies=strategies,
        instruments=instruments,
        history_messages=recommendations,
        composer_default_open=False,
    )
    current_list_path = _author_recommendations_list_path(
        q=q,
        status_filter=status_filter,
        sort_by=sort_by,
        direction=direction,
    )
    return templates.TemplateResponse(
        request,
        "author/message_form.html",
        {
            "title": "Сообщения автора",
            "user": user,
            "author": author,
            "recommendations": recommendations,
            "recommendations_json": serialize_recommendations(recommendations),
            "q": q,
            "status_filter": status_filter,
            "sort_by": sort_by,
            "direction": direction,
            "date_from": date_from,
            "date_to": date_to,
            "inline_next_path": current_list_path,
            "inline_error": inline_error,
            "inline_field_errors": inline_field_errors or {},
            "inline_form_values": _normalize_inline_message_form_values(inline_form_values, instruments),
            **composer_context,
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
    inline_mode: bool,
    error_text: str,
) -> Response:
    if inline_mode:
        inline_feedback = _build_inline_recommendation_feedback(error_text)
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
            inline_form_values=_build_inline_message_form_values(form),
            inline_field_errors=inline_feedback["field_errors"],
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    feedback = _build_recommendation_form_feedback(error_text)
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
            "message_type": str(form.get("message_type", "") or form.get("message_mode", "") or "mixed"),
            "structured_instrument_id": str(form.get("structured_instrument_id", "") or ""),
            "structured_instrument_query": str(form.get("structured_instrument_query", "") or ""),
            "structured_instrument_ticker": str(form.get("structured_instrument_ticker", "") or ""),
            "structured_instrument_name": str(form.get("structured_instrument_name", "") or ""),
            "structured_amount": str(form.get("structured_amount", "") or ""),
            "structured_side": str(form.get("structured_side", "") or ""),
            "structured_price": str(form.get("structured_price", "") or ""),
            "structured_quantity": str(form.get("structured_quantity", "") or ""),
            "structured_tp": str(form.get("structured_tp", "") or ""),
            "structured_sl": str(form.get("structured_sl", "") or ""),
            "structured_note": str(form.get("structured_note", "") or ""),
            "requires_moderation": author.requires_moderation,
            "scheduled_for": str(form.get("scheduled_for", "") or ""),
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
        if recommendation is None or getattr(recommendation.status, "value", recommendation.status) != MessageStatus.PUBLISHED.value or was_published:
            return

        bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
        if isinstance(repository, FileAuthorRepository):
            await deliver_message_notifications_file(
                repository.graph,
                repository.store,
                recommendation,
                bot,
                trigger=trigger,
            )
            return
        if isinstance(repository, SqlAlchemyAuthorRepository):
            await deliver_message_notifications(
                repository.session,
                recommendation,
                bot,
                trigger=trigger,
            )
            return
        logger.warning(
            "Skipping immediate notification delivery for message %s: unsupported repository %s",
            recommendation_id,
            type(repository).__name__,
        )
    except Exception:
        logger.exception("Immediate notification delivery failed for message %s", recommendation_id)
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


def _build_recommendation_form_feedback(error_text: str) -> dict[str, object]:
    field_errors: dict[str, str] = {}
    if error_text == "Выберите стратегию автора.":
        field_errors["strategy_id"] = "Выберите стратегию автора"
    if error_text == "Инструмент не найден по точному тикеру. Укажите корректный symbol.":
        field_errors["structured_instrument_query"] = "Укажите корректный symbol"
    return {"error": _friendly_recommendation_error_message(error_text), "field_errors": field_errors}


def _build_inline_recommendation_feedback(error_text: str) -> dict[str, object]:
    field_errors: dict[str, str] = {}
    if error_text == "Выберите стратегию автора.":
        field_errors["strategy_id"] = "Выберите стратегию автора"
    return {"error": _friendly_recommendation_error_message(error_text), "field_errors": field_errors}


def _friendly_recommendation_error_message(error_text: str) -> str:
    if error_text == "Для structured message нужны инструмент, цена и количество.":
        return "Для structured сообщения укажите инструмент, цену и количество."
    if error_text == "Для structured message нужен инструмент.":
        return "Выберите инструмент для structured сообщения."
    if error_text == "Инструмент не найден по точному тикеру. Укажите корректный symbol.":
        return "Инструмент не найден по точному тикеру. Укажите корректный symbol."
    if error_text == "Для structured message нужно выбрать Buy или Sell.":
        return "Выберите Buy или Sell для structured сообщения."
    if error_text == "Для structured message нужна цена.":
        return "Укажите цену для structured сообщения."
    if error_text == "Для structured message нужно количество.":
        return "Укажите количество для structured сообщения."
    if error_text == "Для mixed message нужен хотя бы один блок контента.":
        return "Заполните хотя бы один блок: описание, OnePager или structured сделку."
    if error_text == "Для text message нужен текст сообщения.":
        return "Введите текст сообщения."
    if error_text in {"Для document message нужен PDF или JPG.", "Для document message нужен документ."}:
        return "Прикрепите PDF или JPG."
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


def _watchlist_candidate_payload(candidate: WatchlistCandidate) -> dict[str, str]:
    return {
        "id": candidate.id,
        "ticker": candidate.ticker,
        "name": candidate.name,
        "board": candidate.board,
        "source": candidate.source,
    }


def _build_history_grid_rows(messages) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for message in messages or []:
        content = message.text or {}
        plain = ""
        body = ""
        if isinstance(content, dict):
            plain = str(content.get("plain") or "").strip()
            body = str(content.get("body") or "").strip()
        preview_full = plain or (re.sub(r"<[^>]+>", "", body).strip() if body else "") or str(message.comment or "Без текста").strip()
        if not preview_full:
            preview_full = "Без текста"
        rows.append(
            {
                "date": (message.updated or message.created).strftime("%d.%m.%Y %H:%M") if message.updated or message.created else "—",
                "type": (message.type or "mixed").upper(),
                "preview": preview_full[:60] + ("..." if len(preview_full) > 60 else ""),
                "preview_full": preview_full,
                "strategy": message.strategy.title if message.strategy else "—",
                "status": label_message_status(message.status),
                "channels": ", ".join(message.deliver) if message.deliver else "strategy",
                "edit_url": f"/author/messages/{message.id}/edit",
            }
        )
    return rows


def _safe_author_next_path(next_path: str) -> str:
    normalized = next_path.strip()
    if not normalized.startswith("/author/"):
        return ""
    return normalized


async def _get_composer_context(
    repository: AuthorRepository,
    author: AuthorProfile,
    *,
    recommendation: Message | None = None,
    form_values: dict[str, object] | None = None,
    strategies: list[Strategy] | None = None,
    instruments: list[Instrument] | None = None,
    instrument_items: list[dict[str, object]] | None = None,
    history_messages: list[Message] | None = None,
    composer_default_open: bool = False,
) -> dict[str, object]:
    loaded_strategies = strategies if strategies is not None else await list_author_strategies(repository, author)
    loaded_instruments = instruments if instruments is not None else await list_active_instruments(repository)
    if instrument_items is None:
        logger.info(
            "Building instrument payloads for %d instruments, provider_enabled=%s",
            len(loaded_instruments),
            get_settings().instrument_quotes.provider_enabled,
        )
        instrument_items = await build_instrument_payloads(loaded_instruments, allow_live_fetch=False)
    if form_values is None:
        form_values = recommendation_form_values(recommendation)
    if history_messages is None:
        history_messages = [recommendation] if recommendation is not None else []
    return {
        "strategies": loaded_strategies,
        "instruments": loaded_instruments,
        "instrument_items": instrument_items,
        "composer_recommendation": recommendation,
        "compose_form_values": form_values,
        "composer_default_open": composer_default_open,
        "history_messages": history_messages,
        "history_json": _build_history_grid_rows(history_messages),
        "show_history": True,
    }


def _unique_instruments_by_id(instruments: list[Instrument]) -> list[Instrument]:
    unique: list[Instrument] = []
    seen: set[str] = set()
    for item in instruments:
        key = str(getattr(item, "id", "") or getattr(item, "ticker", "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _index_instrument_items(instrument_items: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    indexed: dict[str, dict[str, object]] = {}
    for item in instrument_items:
        item_id = str(item.get("id") or "").strip()
        if item_id:
            indexed[item_id] = item
    return indexed


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
        return "/author/messages"
    return f"/author/messages?{urlencode(params)}"


def _derive_message_type_value(
    *,
    text_value: str,
    documents,
    structured_instrument_id: str,
    structured_side_value: str,
    structured_price_value: str,
    structured_quantity_value: str,
    structured_tp_value: str,
    structured_sl_value: str,
    structured_note_value: str,
) -> str:
    has_text = bool(text_value.strip())
    has_documents = bool(documents)
    has_structured = any(
        str(value).strip()
        for value in (
            structured_instrument_id,
            structured_side_value,
            structured_price_value,
            structured_quantity_value,
            structured_tp_value,
            structured_sl_value,
            structured_note_value,
        )
    )
    has_deal = has_structured
    sections = sum(1 for flag in (has_text, has_documents, has_deal) if flag)
    if sections <= 0:
        return "mixed"
    if sections == 1:
        if has_text:
            return "text"
        if has_documents:
            return "document"
        return "deal"
    return "mixed"


def _build_recommendation_prefill_form_values(*, request: Request, author: AuthorProfile) -> dict[str, object]:
    form_values = recommendation_form_values(None)
    form_values.update(
        {
            "strategy_id": str(request.query_params.get("strategy_id", "") or ""),
            "kind": str(request.query_params.get("kind", form_values["kind"]) or form_values["kind"]),
            "status": str(request.query_params.get("status", form_values["status"]) or form_values["status"]),
            "title": str(request.query_params.get("title", "") or ""),
            "message_type": str(request.query_params.get("message_type", request.query_params.get("message_mode", "mixed")) or "mixed"),
            "message_mode": str(request.query_params.get("message_type", request.query_params.get("message_mode", "mixed")) or "mixed"),
            "message_text": str(request.query_params.get("message_text", "") or ""),
            "document_caption": str(request.query_params.get("document_caption", "") or ""),
            "structured_instrument_id": str(request.query_params.get("structured_instrument_id", "") or ""),
            "structured_instrument_query": str(request.query_params.get("structured_instrument_query", "") or ""),
            "structured_side": str(request.query_params.get("structured_side", "") or ""),
            "structured_price": str(request.query_params.get("structured_price", "") or ""),
            "structured_quantity": str(request.query_params.get("structured_quantity", "1") or "1"),
            "structured_amount": str(request.query_params.get("structured_amount", "") or ""),
            "structured_tp": str(request.query_params.get("structured_tp", "") or ""),
            "structured_sl": str(request.query_params.get("structured_sl", "") or ""),
            "structured_note": str(request.query_params.get("structured_note", "") or ""),
            "requires_moderation": author.requires_moderation,
            "scheduled_for": str(request.query_params.get("scheduled_for", "") or ""),
        }
    )
    return form_values


async def _resolve_structured_instrument_selection(
    repository: AuthorRepository,
    instruments: list[Instrument],
    *,
    selected_instrument_id: str,
    structured_instrument_query: str,
) -> tuple[Instrument | None, str]:
    selected_instrument = next((item for item in instruments if item.id == selected_instrument_id), None)
    if selected_instrument is not None:
        return selected_instrument, selected_instrument.id

    normalized_query = structured_instrument_query.strip()
    if not normalized_query:
        return None, ""

    imported_instrument = await get_or_import_instrument_by_symbol(repository, normalized_query)
    if imported_instrument is None:
        raise ValueError("Инструмент не найден по точному тикеру. Укажите корректный symbol.")
    return imported_instrument, imported_instrument.id


def _normalize_inline_message_form_values(
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


def _build_inline_message_form_values(form) -> dict[str, str]:
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
        items = [item for item in items if getattr(item.status, "value", item.status) == status_filter]
    if not normalized:
        return items
    return [
        item
        for item in items
        if normalized in " ".join(
            part.lower()
            for part in [
                item.title or "",
                getattr(item, "comment", "") or "",
                (item.text or {}).get("plain", "") if isinstance(getattr(item, "text", None), dict) else "",
                item.strategy.title if item.strategy is not None else "",
                getattr(item.status, "value", item.status),
                getattr(item.kind, "value", item.kind),
                " ".join(item.deliver or []) if getattr(item, "deliver", None) else "",
                " ".join((deal.get("instrument_id", "") for deal in (item.deals or []))) if getattr(item, "deals", None) else "",
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
        key = lambda item: (getattr(item, "updated", None), getattr(item, "created", None))
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
