from __future__ import annotations

import logging
from urllib.parse import quote, urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.repositories import get_auth_repository, get_public_repository
from pitchcopytrade.auth.session import (
    get_telegram_fallback_cookie_name,
    get_user_from_session_token,
    get_user_from_telegram_fallback_cookie,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.db.models.enums import LegalDocumentType
from pitchcopytrade.api.request_trace import (
    attach_journey_cookie,
    checkout_validation_reason,
    get_entry_marker,
    get_or_create_journey_id,
    log_request_trace,
)
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.repositories.contracts import AuthRepository, PublicRepository
from pitchcopytrade.services.legal_documents import read_legal_document_markdown
from pitchcopytrade.services.payment_sync import process_tbank_callback
from pitchcopytrade.services.public import (
    AlreadySubscribedError,
    CheckoutRequest,
    build_strategy_story,
    create_stub_checkout,
    get_public_product,
    get_public_strategy_by_slug,
    list_active_checkout_documents,
    list_public_strategies,
)
from pitchcopytrade.services.instruments import build_strategy_quote_strip
from pitchcopytrade.services.subscriber import billing_period_label
from pitchcopytrade.web.templates import templates


router = APIRouter(tags=["public"])
logger = logging.getLogger(__name__)


async def _read_request_payload(request: Request) -> dict[str, object]:
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        payload = await request.json()
        return payload if isinstance(payload, dict) else {}
    form = await request.form()
    return {key: value for key, value in form.items()}


async def _resolve_request_identity(
    request: Request,
    auth_repository: AuthRepository | None,
) -> tuple[str | None, int | None]:
    if auth_repository is None:
        return None, None
    session_token = request.cookies.get(get_settings().auth.session_cookie_name)
    if not session_token:
        return None, None
    user = await get_user_from_session_token(auth_repository, session_token)
    if user is None:
        return None, None
    return user.id, user.telegram_user_id


async def _resolve_current_user(
    request: Request,
    auth_repository: AuthRepository | None,
):
    if auth_repository is None:
        return None
    session_token = request.cookies.get(get_settings().auth.session_cookie_name)
    if session_token:
        user = await get_user_from_session_token(auth_repository, session_token)
        if user is not None:
            return user
    tg_cookie = request.cookies.get(get_telegram_fallback_cookie_name())
    if not tg_cookie:
        return None
    return await get_user_from_telegram_fallback_cookie(auth_repository, tg_cookie)


def _with_entry_marker(url: str, entry_marker: str | None) -> str:
    if not entry_marker:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}entry={quote(entry_marker, safe='')}"


def _append_query_param(url: str, key: str, value: str) -> str:
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}{key}={quote(value, safe='')}"


def _wants_json_response(request: Request) -> bool:
    return "application/json" in request.headers.get("accept", "").lower()


def _verify_redirect_url(requested_next: str) -> str:
    return f"/verify/telegram?next=/app/catalog&requested_next={quote(requested_next, safe='/')}"


@router.get("/", include_in_schema=False)
async def root() -> Response:
    return RedirectResponse(url="/catalog", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/miniapp", include_in_schema=False)
async def miniapp_root(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, telegram_user_id = await _resolve_request_identity(request, auth_repository)
    entry_marker = get_entry_marker(request) or "miniapp_bootstrap"
    tg_cookie = request.cookies.get(get_telegram_fallback_cookie_name())
    if tg_cookie:
        tg_user = await get_user_from_telegram_fallback_cookie(auth_repository, tg_cookie)
        if tg_user is not None:
            log_request_trace(
                logger,
                request,
                stage="miniapp_root",
                journey_id=journey_id,
                surface="bootstrap",
                auth_user_id=tg_user.id,
                telegram_user_id=tg_user.telegram_user_id,
                entry_marker=entry_marker,
                entry_id=journey_id,
                entry_surface="bootstrap",
                first_html_surface="redirect_catalog",
                requested_next="/app/catalog",
                block_reason="has_telegram_cookie",
            )
            response = RedirectResponse(url="/app/catalog", status_code=status.HTTP_303_SEE_OTHER)
            return attach_journey_cookie(response, journey_id)
    log_request_trace(
        logger,
        request,
        stage="miniapp_root",
        journey_id=journey_id,
        surface="bootstrap",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="bootstrap",
        first_html_surface="miniapp_entry",
        requested_next="/app/catalog",
        block_reason="render_miniapp_entry",
    )
    response = templates.TemplateResponse(
        request,
        "app/miniapp_entry.html",
        {
            "title": "PitchCopyTrade",
            "bot_url": f"https://t.me/{get_settings().telegram.bot_username}",
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/verify/telegram", response_class=HTMLResponse)
async def telegram_verify_page(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, telegram_user_id = await _resolve_request_identity(request, auth_repository)
    entry_marker = get_entry_marker(request) or "verify_telegram"
    requested_next = str(request.query_params.get("requested_next", "") or "") or str(request.query_params.get("next", "") or "/app/catalog")
    log_request_trace(
        logger,
        request,
        stage="verify_page",
        journey_id=journey_id,
        surface="verify",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="verify",
        first_html_surface="telegram_verify",
        requested_next=requested_next,
    )
    response = templates.TemplateResponse(
        request,
        "public/telegram_verify.html",
        {
            "title": "Подтверждение через Telegram",
            "telegram_bot_username": get_settings().telegram.bot_username,
            "surface_next": "/app/catalog",
            "requested_next": requested_next,
            "base_url": get_settings().app.base_url,
            "webapp_enabled": get_settings().app.base_url.startswith("https://"),
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, telegram_user_id = await _resolve_request_identity(request, auth_repository)
    entry_marker = get_entry_marker(request) or "public_catalog"
    current_user = await _resolve_current_user(request, auth_repository)
    user_active_product_ids = (
        await repository.list_active_product_ids_for_user(current_user.id)
        if current_user is not None and current_user.id
        else set()
    )
    strategies = await list_public_strategies(repository)
    for strategy in strategies:
        strategy.detail_href = _with_entry_marker(f"/catalog/strategies/{strategy.slug}", "public_catalog")
        for product in strategy.subscription_products:
            product.checkout_href = _with_entry_marker(f"/checkout/{product.slug}", "public_catalog")
        strategy.story = build_strategy_story(strategy)
        strategy.quotes = await build_strategy_quote_strip(strategy)
    response = templates.TemplateResponse(
        request,
        "public/catalog.html",
        {
            "title": "Каталог PitchCopyTrade",
            "strategies": strategies,
            "telegram_bot_username": get_settings().telegram.bot_username,
            "miniapp_mode": False,
            "entry_marker": entry_marker,
            "user_active_product_ids": user_active_product_ids,
        },
    )
    log_request_trace(
        logger,
        request,
        stage="catalog_render",
        journey_id=journey_id,
        surface="public",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="public",
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/catalog/strategies/{slug}", response_class=HTMLResponse)
async def strategy_detail_page(
    slug: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, telegram_user_id = await _resolve_request_identity(request, auth_repository)
    entry_marker = get_entry_marker(request) or "public_strategy"
    current_user = await _resolve_current_user(request, auth_repository)
    user_active_product_ids = (
        await repository.list_active_product_ids_for_user(current_user.id)
        if current_user is not None and current_user.id
        else set()
    )
    strategy = await get_public_strategy_by_slug(repository, slug)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    strategy.story = build_strategy_story(strategy)
    strategy.quotes = await build_strategy_quote_strip(strategy)
    strategy.detail_href = _with_entry_marker(f"/catalog/strategies/{strategy.slug}", "public_strategy")
    for product in strategy.subscription_products:
        product.checkout_href = _with_entry_marker(f"/checkout/{product.slug}", "public_strategy")
    response = templates.TemplateResponse(
        request,
        "public/strategy_detail.html",
        {
            "title": strategy.title,
            "strategy": strategy,
            "miniapp_mode": False,
            "billing_period_label": billing_period_label,
            "entry_marker": entry_marker,
            "user_active_product_ids": user_active_product_ids,
            "already_subscribed_notice": request.query_params.get("notice") == "already_subscribed",
        },
    )
    log_request_trace(
        logger,
        request,
        stage="strategy_render",
        journey_id=journey_id,
        surface="public",
        auth_user_id=auth_user_id,
        telegram_user_id=telegram_user_id,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="public",
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/checkout/{product_ref}", response_class=HTMLResponse)
async def checkout_page(
    product_ref: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, auth_user_telegram_id = await _resolve_request_identity(request, auth_repository)
    product = await get_public_product(repository, product_ref)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    documents = await list_active_checkout_documents(repository)
    checkout_ready = any(document.document_type is LegalDocumentType.DISCLAIMER for document in documents)
    detected_lead_source = _detect_lead_source_name(request)
    telegram_intended = _is_telegram_intended_checkout(request, detected_lead_source)
    entry_marker = get_entry_marker(request) or "public_catalog"
    log_request_trace(
        logger,
        request,
        stage="checkout_render",
        journey_id=journey_id,
        surface="public",
        auth_user_id=auth_user_id,
        telegram_user_id=auth_user_telegram_id,
        rendered_href=_with_entry_marker(f"/checkout/{product_ref}", entry_marker),
        checkout_surface="public",
        telegram_intended=telegram_intended,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="public",
    )
    response = templates.TemplateResponse(
        request,
        "public/checkout.html",
        {
            "title": f"Подписка {product.title}",
            "product": product,
            "documents": documents,
            "checkout_ready": checkout_ready,
            "payment_provider": get_settings().payments.provider,
            "miniapp_mode": False,
            "entry_marker": entry_marker,
            "error": None,
            "form_values": {
                "full_name": "",
                "email": "",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": detected_lead_source,
                "promo_code_value": "",
                "accepted_document_ids": [],
                "entry_id": journey_id,
                "entry_surface": "public",
            },
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/legal/{document_id}", response_class=HTMLResponse)
async def legal_document_page(
    document_id: str,
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    documents = await list_active_checkout_documents(repository)
    document = next((item for item in documents if item.id == document_id), None)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found")
    return templates.TemplateResponse(
        request,
        "public/legal_document.html",
        {
            "title": document.title,
            "document": document,
            "content_md": read_legal_document_markdown(document),
            "miniapp_mode": False,
        },
    )


@router.post("/checkout/{product_ref}", response_class=HTMLResponse)
async def checkout_submit(
    product_ref: str,
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
    auth_repository: AuthRepository = Depends(get_auth_repository),
    full_name: str = Form(""),
    email: str = Form(""),
    timezone_name: str = Form("Europe/Moscow"),
    lead_source_name: str = Form(""),
    accepted_document_ids: list[str] | None = Form(default=None),
    promo_code_value: str = Form(""),
    entry_id: str = Form(""),
    entry_surface: str = Form(""),
) -> Response:
    journey_id = get_or_create_journey_id(request)
    auth_user_id, auth_user_telegram_id = await _resolve_request_identity(request, auth_repository)
    product = await get_public_product(repository, product_ref)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product_title = product.title

    documents = await list_active_checkout_documents(repository)
    checkout_ready = any(document.document_type is LegalDocumentType.DISCLAIMER for document in documents)
    detected_lead_source = lead_source_name.strip() or _detect_lead_source_name(request)
    resolved_entry_id = entry_id.strip() or journey_id
    resolved_entry_surface = entry_surface.strip() or "public"
    entry_marker = get_entry_marker(request) or resolved_entry_surface
    telegram_user_id = None
    telegram_cookie_present = False
    telegram_cookie = request.cookies.get(get_telegram_fallback_cookie_name())
    if telegram_cookie:
        telegram_cookie_present = True
        telegram_user = await get_user_from_telegram_fallback_cookie(auth_repository, telegram_cookie)
        if telegram_user is not None:
            telegram_user_id = telegram_user.telegram_user_id
    telegram_intended = _is_telegram_intended_checkout(request, detected_lead_source)
    logger.info(
        "Public checkout route path=%s referer=%s lead_source=%s telegram_cookie_present=%s auth_user_cookie_present=%s auth_telegram_user_id=%s product_ref=%s",
        request.url.path,
        request.headers.get("referer") or "-",
        detected_lead_source,
        telegram_cookie_present,
        bool(request.cookies.get(get_settings().auth.session_cookie_name)),
        telegram_user_id,
        product_ref,
    )
    log_request_trace(
        logger,
        request,
        stage="checkout_submit",
        journey_id=journey_id,
        surface="public",
        auth_user_id=auth_user_id,
        telegram_user_id=auth_user_telegram_id,
        entry_marker=entry_marker,
        entry_id=resolved_entry_id,
        entry_surface=resolved_entry_surface,
    )
    if telegram_intended and telegram_user_id is None:
        logger.warning(
            "Public checkout blocked for Telegram-intended flow without telegram context: path=%s referer=%s lead_source=%s product_ref=%s",
            request.url.path,
            request.headers.get("referer") or "-",
            detected_lead_source,
            product_ref,
        )
        response = RedirectResponse(url=_verify_redirect_url(f"/checkout/{product_ref}"), status_code=status.HTTP_303_SEE_OTHER)
        log_request_trace(
            logger,
            request,
            stage="checkout_submit_blocked",
            journey_id=journey_id,
            surface="public",
            auth_user_id=auth_user_id,
            telegram_user_id=auth_user_telegram_id,
            rendered_href=_with_entry_marker(f"/checkout/{product_ref}", entry_marker),
            checkout_surface="public",
            telegram_intended=True,
            block_reason="missing_telegram_context",
            entry_marker=entry_marker,
            entry_id=resolved_entry_id,
            entry_surface=resolved_entry_surface,
            first_html_surface="telegram_verify",
            requested_next=f"/checkout/{product_ref}",
        )
        return attach_journey_cookie(response, journey_id)
    try:
        result = await create_stub_checkout(
            repository,
            product=product,
            request=CheckoutRequest(
                full_name=full_name.strip(),
                email=email.strip().lower() or None,
                timezone_name=timezone_name.strip() or "Europe/Moscow",
                accepted_document_ids=accepted_document_ids or [],
                lead_source_name=detected_lead_source,
                promo_code_value=promo_code_value.strip().upper() or None,
                ip_address=request.client.host if request.client else None,
                telegram_user_id=telegram_user_id,
            ),
        )
    except AlreadySubscribedError as exc:
        if _wants_json_response(request):
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_409_CONFLICT)
        redirect_url = "/catalog"
        strategy = getattr(product, "strategy", None)
        strategy_slug = getattr(strategy, "slug", None)
        if strategy_slug:
            redirect_url = f"/catalog/strategies/{strategy_slug}"
        redirect_url = _with_entry_marker(redirect_url, entry_marker)
        redirect_url = _append_query_param(redirect_url, "notice", "already_subscribed")
        response = RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)
        return attach_journey_cookie(response, journey_id)
    except ValueError as exc:
        validation_reason = checkout_validation_reason(str(exc))
        logger.warning(
            "Public checkout invalid path=%s product_ref=%s reason=%s detail=%s",
            request.url.path,
            product_ref,
            validation_reason,
            exc,
        )
        log_request_trace(
            logger,
            request,
            stage="checkout_invalid",
            journey_id=journey_id,
            surface="public",
            auth_user_id=auth_user_id,
            telegram_user_id=auth_user_telegram_id,
            entry_marker=entry_marker,
            entry_id=resolved_entry_id,
            entry_surface=resolved_entry_surface,
            block_reason=validation_reason,
            block_detail=str(exc),
        )
        response = templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product_title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "miniapp_mode": False,
                "entry_marker": entry_marker,
                "error": str(exc),
                "form_values": {
                    "full_name": full_name,
                    "email": email,
                    "timezone_name": timezone_name,
                    "lead_source_name": detected_lead_source,
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids or [],
                    "entry_id": resolved_entry_id,
                    "entry_surface": resolved_entry_surface,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
        return attach_journey_cookie(response, journey_id)
    except Exception:
        logger.exception("Public checkout creation failed for product %s", product_ref)
        response = templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product_title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "miniapp_mode": False,
                "entry_marker": entry_marker,
                "error": "Не удалось создать заявку на оплату. Попробуйте еще раз.",
                "form_values": {
                    "full_name": full_name,
                    "email": email,
                    "timezone_name": timezone_name,
                    "lead_source_name": detected_lead_source,
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids or [],
                    "entry_id": resolved_entry_id,
                    "entry_surface": resolved_entry_surface,
                },
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
        return attach_journey_cookie(response, journey_id)

    response = templates.TemplateResponse(
        request,
        "public/checkout_success.html",
        {
            "title": "Заявка создана",
            "product": product,
            "result": result,
            "payment_provider": get_settings().payments.provider,
            "miniapp_mode": False,
            "entry_marker": entry_marker,
            "entry_id": resolved_entry_id,
            "entry_surface": resolved_entry_surface,
        },
        status_code=status.HTTP_201_CREATED,
    )
    return attach_journey_cookie(response, journey_id)


@router.post("/payments/tbank/notify", include_in_schema=False)
async def tbank_payment_notify(
    request: Request,
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    payload = await _read_request_payload(request)
    settings = get_settings()
    client = TBankAcquiringClient(
        terminal_key=settings.payments.tinkoff_terminal_key.get_secret_value(),
        password=settings.payments.tinkoff_secret_key.get_secret_value(),
    )
    if not client.validate_callback_token(payload):
        return PlainTextResponse("ERROR", status_code=status.HTTP_400_BAD_REQUEST)

    await process_tbank_callback(session, payload=payload)
    return PlainTextResponse("OK")


def _detect_lead_source_name(request: Request) -> str:
    for key in ("utm_source", "source", "lead_source"):
        value = request.query_params.get(key)
        if value:
            return value.strip().lower()

    referer = request.headers.get("referer")
    if referer:
        host = urlparse(referer).hostname or ""
        if "t.me" in host or "telegram" in host:
            return "telegram"

    return "website"


def _is_telegram_intended_checkout(request: Request, lead_source_name: str) -> bool:
    if lead_source_name == "telegram_miniapp":
        return True
    referer = request.headers.get("referer") or ""
    if not referer:
        return False
    parsed = urlparse(referer)
    return parsed.path.startswith("/app/") or parsed.path.startswith("/miniapp")
