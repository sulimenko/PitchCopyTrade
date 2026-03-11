from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.services.public import (
    CheckoutRequest,
    create_stub_checkout,
    get_public_product,
    get_public_strategy_by_slug,
    list_active_checkout_documents,
    list_public_strategies,
)
from pitchcopytrade.services.legal_documents import read_legal_document_markdown
from pitchcopytrade.web.templates import templates


router = APIRouter(tags=["public"])


@router.get("/", include_in_schema=False)
async def root() -> Response:
    return RedirectResponse(url="/catalog", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/miniapp", include_in_schema=False)
async def miniapp_root() -> Response:
    return RedirectResponse(url="/catalog?surface=miniapp", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/catalog", response_class=HTMLResponse)
async def catalog_page(request: Request, session: AsyncSession = Depends(get_db_session)) -> Response:
    strategies = await list_public_strategies(session)
    return templates.TemplateResponse(
        request,
        "public/catalog.html",
        {
            "title": "PitchCopyTrade Catalog",
            "strategies": strategies,
            "surface": request.query_params.get("surface", "web"),
            "telegram_bot_username": get_settings().telegram.bot_username,
        },
    )


@router.get("/catalog/strategies/{slug}", response_class=HTMLResponse)
async def strategy_detail_page(
    slug: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    strategy = await get_public_strategy_by_slug(session, slug)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return templates.TemplateResponse(
        request,
        "public/strategy_detail.html",
        {
            "title": strategy.title,
            "strategy": strategy,
        },
    )


@router.get("/checkout/{product_id}", response_class=HTMLResponse)
async def checkout_page(
    product_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    product = await get_public_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    documents = await list_active_checkout_documents(session)
    checkout_ready = len(documents) == 4
    return templates.TemplateResponse(
        request,
        "public/checkout.html",
        {
            "title": f"Checkout {product.title}",
            "product": product,
            "documents": documents,
            "checkout_ready": checkout_ready,
            "error": None,
            "form_values": {
                "full_name": "",
                "email": "",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "",
                "accepted_document_ids": [],
            },
        },
    )


@router.get("/legal/{document_id}", response_class=HTMLResponse)
async def legal_document_page(
    document_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    documents = await list_active_checkout_documents(session)
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
        },
    )


@router.post("/checkout/{product_id}", response_class=HTMLResponse)
async def checkout_submit(
    product_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db_session),
    full_name: str = Form(""),
    email: str = Form(""),
    timezone_name: str = Form("Europe/Moscow"),
    lead_source_name: str = Form(""),
    accepted_document_ids: list[str] = Form(...),
) -> Response:
    product = await get_public_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    documents = await list_active_checkout_documents(session)
    checkout_ready = len(documents) == 4
    try:
        result = await create_stub_checkout(
            session,
            product=product,
            request=CheckoutRequest(
                full_name=full_name.strip(),
                email=email.strip().lower() or None,
                timezone_name=timezone_name.strip() or "Europe/Moscow",
                accepted_document_ids=accepted_document_ids,
                lead_source_name=lead_source_name.strip() or None,
                ip_address=request.client.host if request.client else None,
            ),
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Checkout {product.title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "error": str(exc),
                "form_values": {
                    "full_name": full_name,
                    "email": email,
                    "timezone_name": timezone_name,
                    "lead_source_name": lead_source_name,
                    "accepted_document_ids": accepted_document_ids,
                },
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return templates.TemplateResponse(
        request,
        "public/checkout_success.html",
        {
            "title": "Checkout Created",
            "product": product,
            "result": result,
        },
        status_code=status.HTTP_201_CREATED,
    )
