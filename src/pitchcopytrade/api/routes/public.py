from __future__ import annotations

import logging
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.repositories import get_public_repository
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.payments.tbank import TBankAcquiringClient
from pitchcopytrade.repositories.contracts import PublicRepository
from pitchcopytrade.services.legal_documents import read_legal_document_markdown
from pitchcopytrade.services.payment_sync import process_tbank_callback
from pitchcopytrade.services.public import (
    CheckoutRequest,
    create_stub_checkout,
    build_strategy_story,
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


@router.get("/", include_in_schema=False)
async def root() -> Response:
    return RedirectResponse(url="/catalog", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/miniapp", include_in_schema=False)
async def miniapp_root(request: Request) -> Response:
    return templates.TemplateResponse(
        request,
        "public/miniapp_bootstrap.html",
        {
            "title": "PitchCopyTrade Mini App",
            "telegram_bot_username": get_settings().telegram.bot_username,
            "next_path": "/app/catalog",
            "base_url": get_settings().app.base_url,
            "webapp_enabled": get_settings().app.base_url.startswith("https://"),
        },
    )


@router.get("/verify/telegram", response_class=HTMLResponse)
async def telegram_verify_page(request: Request) -> Response:
    return templates.TemplateResponse(
        request,
        "public/telegram_verify.html",
        {
            "title": "Подтверждение через Telegram",
            "telegram_bot_username": get_settings().telegram.bot_username,
            "surface_next": request.query_params.get("next", "/app/catalog"),
            "base_url": get_settings().app.base_url,
            "webapp_enabled": get_settings().app.base_url.startswith("https://"),
        },
    )


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    strategies = await list_public_strategies(repository)
    for strategy in strategies:
        strategy.story = build_strategy_story(strategy)
        strategy.quotes = await build_strategy_quote_strip(strategy)
    return templates.TemplateResponse(
        request,
        "public/catalog.html",
        {
            "title": "Каталог PitchCopyTrade",
            "strategies": strategies,
            "telegram_bot_username": get_settings().telegram.bot_username,
            "miniapp_mode": False,
        },
    )


@router.get("/catalog/strategies/{slug}", response_class=HTMLResponse)
async def strategy_detail_page(
    slug: str,
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    strategy = await get_public_strategy_by_slug(repository, slug)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    strategy.story = build_strategy_story(strategy)
    strategy.quotes = await build_strategy_quote_strip(strategy)
    return templates.TemplateResponse(
        request,
        "public/strategy_detail.html",
        {
            "title": strategy.title,
            "strategy": strategy,
            "miniapp_mode": False,
            "billing_period_label": billing_period_label,
        },
    )


@router.get("/checkout/{product_id}", response_class=HTMLResponse)
async def checkout_page(
    product_id: str,
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    product = await get_public_product(repository, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    documents = await list_active_checkout_documents(repository)
    checkout_ready = len(documents) == 4
    return templates.TemplateResponse(
        request,
        "public/checkout.html",
        {
            "title": f"Подписка {product.title}",
            "product": product,
            "documents": documents,
            "checkout_ready": checkout_ready,
            "payment_provider": get_settings().payments.provider,
            "miniapp_mode": False,
            "error": None,
            "form_values": {
                "full_name": "",
                "email": "",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": _detect_lead_source_name(request),
                "promo_code_value": "",
                "accepted_document_ids": [],
            },
        },
    )


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


@router.post("/checkout/{product_id}", response_class=HTMLResponse)
async def checkout_submit(
    product_id: str,
    request: Request,
    repository: PublicRepository = Depends(get_public_repository),
    full_name: str = Form(""),
    email: str = Form(""),
    timezone_name: str = Form("Europe/Moscow"),
    lead_source_name: str = Form(""),
    accepted_document_ids: list[str] = Form(...),
    promo_code_value: str = Form(""),
) -> Response:
    product = await get_public_product(repository, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    documents = await list_active_checkout_documents(repository)
    checkout_ready = len(documents) == 4
    detected_lead_source = lead_source_name.strip() or _detect_lead_source_name(request)
    try:
        result = await create_stub_checkout(
            repository,
            product=product,
            request=CheckoutRequest(
                full_name=full_name.strip(),
                email=email.strip().lower() or None,
                timezone_name=timezone_name.strip() or "Europe/Moscow",
                accepted_document_ids=accepted_document_ids,
                lead_source_name=detected_lead_source,
                promo_code_value=promo_code_value.strip().upper() or None,
                ip_address=request.client.host if request.client else None,
            ),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product.title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "miniapp_mode": False,
                "error": str(exc),
                "form_values": {
                    "full_name": full_name,
                    "email": email,
                    "timezone_name": timezone_name,
                    "lead_source_name": detected_lead_source,
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    except Exception:
        logger.exception("Public checkout creation failed for product %s", product_id)
        return templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product.title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "miniapp_mode": False,
                "error": "Не удалось создать заявку на оплату. Попробуйте еще раз.",
                "form_values": {
                    "full_name": full_name,
                    "email": email,
                    "timezone_name": timezone_name,
                    "lead_source_name": detected_lead_source,
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids,
                },
            },
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    return templates.TemplateResponse(
        request,
        "public/checkout_success.html",
        {
            "title": "Заявка создана",
            "product": product,
            "result": result,
            "payment_provider": get_settings().payments.provider,
            "miniapp_mode": False,
        },
        status_code=status.HTTP_201_CREATED,
    )


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
