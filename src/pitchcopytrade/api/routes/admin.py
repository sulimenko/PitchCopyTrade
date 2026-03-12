from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import require_admin
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import BillingPeriod, LegalDocumentType, ProductType, RiskLevel, StrategyStatus
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.services.admin import (
    ProductFormData,
    apply_manual_discount_to_payment,
    confirm_payment_and_activate_subscription,
    StrategyFormData,
    create_product,
    create_strategy,
    get_admin_subscription,
    get_admin_payment,
    get_admin_product,
    get_admin_dashboard_stats,
    get_payment_review_stats,
    get_admin_strategy,
    list_admin_authors,
    list_admin_bundles,
    list_admin_payments,
    list_admin_products,
    list_admin_subscriptions,
    list_admin_strategies,
    update_product,
    update_strategy,
)
from pitchcopytrade.services.delivery_admin import (
    get_admin_delivery_record,
    list_admin_delivery_records,
    retry_recommendation_delivery,
)
from pitchcopytrade.services.legal_admin import (
    LegalDocumentFormData,
    activate_admin_legal_document,
    create_admin_legal_document,
    get_admin_legal_document,
    list_admin_legal_documents,
    update_admin_legal_document,
)
from pitchcopytrade.services.lead_analytics import list_lead_source_analytics
from pitchcopytrade.services.legal_documents import read_legal_document_markdown
from pitchcopytrade.services.promo_admin import (
    PromoCodeFormData,
    create_admin_promo_code,
    get_admin_promo_code,
    list_admin_promo_codes,
    update_admin_promo_code,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("", include_in_schema=False)
async def admin_root() -> Response:
    return RedirectResponse(url="/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/dashboard", response_class=HTMLResponse)
async def admin_dashboard(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    stats = await get_admin_dashboard_stats(session)
    strategies = await list_admin_strategies(session)
    products = await list_admin_products(session)
    payments = await list_admin_payments(session)
    subscriptions = await list_admin_subscriptions(session)
    return templates.TemplateResponse(
        request,
        "admin/dashboard.html",
        {
            "title": "PitchCopyTrade Admin",
            "user": user,
            "stats": stats,
            "recent_strategies": strategies[:5],
            "recent_products": products[:5],
            "recent_payments": payments[:5],
            "recent_subscriptions": subscriptions[:5],
        },
    )


@router.get("/strategies", response_class=HTMLResponse)
async def strategy_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    strategies = await list_admin_strategies(session)
    return templates.TemplateResponse(
        request,
        "admin/strategies_list.html",
        {
            "title": "Стратегии",
            "user": user,
            "strategies": strategies,
        },
    )


@router.get("/strategies/new", response_class=HTMLResponse)
async def strategy_create_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    return await _render_strategy_form(
        request=request,
        user=user,
        session=session,
        strategy=None,
        error=None,
        form_values={},
    )


@router.post("/strategies", response_class=HTMLResponse)
async def strategy_create_submit(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    author_id: str = Form(...),
    slug: str = Form(...),
    title: str = Form(...),
    short_description: str = Form(...),
    full_description: str = Form(""),
    risk_level: str = Form(...),
    status_value: str = Form(..., alias="status"),
    min_capital_rub: str = Form(""),
    is_public: str | None = Form(default=None),
) -> Response:
    try:
        data = _build_strategy_form_data(
            author_id=author_id,
            slug=slug,
            title=title,
            short_description=short_description,
            full_description=full_description,
            risk_level=risk_level,
            status_value=status_value,
            min_capital_rub=min_capital_rub,
            is_public=is_public,
        )
        strategy = await create_strategy(session, data)
    except ValueError as exc:
        return await _render_strategy_form(
            request=request,
            user=user,
            session=session,
            strategy=None,
            error=str(exc),
            form_values={
                "author_id": author_id,
                "slug": slug,
                "title": title,
                "short_description": short_description,
                "full_description": full_description,
                "risk_level": risk_level,
                "status": status_value,
                "min_capital_rub": min_capital_rub,
                "is_public": is_public is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(
        url=f"/admin/strategies/{strategy.id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/strategies/{strategy_id}/edit", response_class=HTMLResponse)
async def strategy_edit_page(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    strategy = await get_admin_strategy(session, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return await _render_strategy_form(
        request=request,
        user=user,
        session=session,
        strategy=strategy,
        error=None,
        form_values=_form_values_from_strategy(strategy),
    )


@router.post("/strategies/{strategy_id}", response_class=HTMLResponse)
async def strategy_edit_submit(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    author_id: str = Form(...),
    slug: str = Form(...),
    title: str = Form(...),
    short_description: str = Form(...),
    full_description: str = Form(""),
    risk_level: str = Form(...),
    status_value: str = Form(..., alias="status"),
    min_capital_rub: str = Form(""),
    is_public: str | None = Form(default=None),
) -> Response:
    strategy = await get_admin_strategy(session, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    try:
        data = _build_strategy_form_data(
            author_id=author_id,
            slug=slug,
            title=title,
            short_description=short_description,
            full_description=full_description,
            risk_level=risk_level,
            status_value=status_value,
            min_capital_rub=min_capital_rub,
            is_public=is_public,
        )
        await update_strategy(session, strategy, data)
    except ValueError as exc:
        return await _render_strategy_form(
            request=request,
            user=user,
            session=session,
            strategy=strategy,
            error=str(exc),
            form_values={
                "author_id": author_id,
                "slug": slug,
                "title": title,
                "short_description": short_description,
                "full_description": full_description,
                "risk_level": risk_level,
                "status": status_value,
                "min_capital_rub": min_capital_rub,
                "is_public": is_public is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )

    return RedirectResponse(
        url=f"/admin/strategies/{strategy.id}/edit",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/products", response_class=HTMLResponse)
async def product_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    products = await list_admin_products(session)
    return templates.TemplateResponse(
        request,
        "admin/products_list.html",
        {
            "title": "Продукты подписки",
            "user": user,
            "products": products,
        },
    )


@router.get("/products/new", response_class=HTMLResponse)
async def product_create_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    return await _render_product_form(
        request=request,
        user=user,
        session=session,
        product=None,
        error=None,
        form_values={},
    )


@router.get("/promos", response_class=HTMLResponse)
async def promo_code_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    promo_codes = await list_admin_promo_codes(session)
    stats = {
        "active": sum(1 for item in promo_codes if item.is_active),
        "inactive": sum(1 for item in promo_codes if not item.is_active),
        "redeemed": sum(item.current_redemptions for item in promo_codes),
    }
    return templates.TemplateResponse(
        request,
        "admin/promos_list.html",
        {
            "title": "Промокоды",
            "user": user,
            "promo_codes": promo_codes,
            "stats": stats,
        },
    )


@router.get("/promos/new", response_class=HTMLResponse)
async def promo_code_create_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    return await _render_promo_form(
        request=request,
        user=user,
        session=session,
        promo_code=None,
        error=None,
        form_values={},
    )


@router.post("/promos", response_class=HTMLResponse)
async def promo_code_create_submit(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    code: str = Form(...),
    description: str = Form(""),
    discount_percent: str = Form(""),
    discount_amount_rub: str = Form(""),
    max_redemptions: str = Form(""),
    expires_at: str = Form(""),
    is_active: str | None = Form(default=None),
) -> Response:
    try:
        data = _build_promo_form_data(
            code=code,
            description=description,
            discount_percent=discount_percent,
            discount_amount_rub=discount_amount_rub,
            max_redemptions=max_redemptions,
            expires_at=expires_at,
            is_active=is_active,
        )
        promo_code = await create_admin_promo_code(session, data)
    except ValueError as exc:
        return await _render_promo_form(
            request=request,
            user=user,
            session=session,
            promo_code=None,
            error=str(exc),
            form_values={
                "code": code,
                "description": description,
                "discount_percent": discount_percent,
                "discount_amount_rub": discount_amount_rub,
                "max_redemptions": max_redemptions,
                "expires_at": expires_at,
                "is_active": is_active is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/promos/{promo_code.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/promos/{promo_code_id}/edit", response_class=HTMLResponse)
async def promo_code_edit_page(
    promo_code_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    promo_code = await get_admin_promo_code(session, promo_code_id)
    if promo_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")
    return await _render_promo_form(
        request=request,
        user=user,
        session=session,
        promo_code=promo_code,
        error=None,
        form_values=_form_values_from_promo_code(promo_code),
    )


@router.post("/promos/{promo_code_id}", response_class=HTMLResponse)
async def promo_code_edit_submit(
    promo_code_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    code: str = Form(...),
    description: str = Form(""),
    discount_percent: str = Form(""),
    discount_amount_rub: str = Form(""),
    max_redemptions: str = Form(""),
    expires_at: str = Form(""),
    is_active: str | None = Form(default=None),
) -> Response:
    promo_code = await get_admin_promo_code(session, promo_code_id)
    if promo_code is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Promo code not found")

    try:
        data = _build_promo_form_data(
            code=code,
            description=description,
            discount_percent=discount_percent,
            discount_amount_rub=discount_amount_rub,
            max_redemptions=max_redemptions,
            expires_at=expires_at,
            is_active=is_active,
        )
        await update_admin_promo_code(session, promo_code, data)
    except ValueError as exc:
        return await _render_promo_form(
            request=request,
            user=user,
            session=session,
            promo_code=promo_code,
            error=str(exc),
            form_values={
                "code": code,
                "description": description,
                "discount_percent": discount_percent,
                "discount_amount_rub": discount_amount_rub,
                "max_redemptions": max_redemptions,
                "expires_at": expires_at,
                "is_active": is_active is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/promos/{promo_code.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/products", response_class=HTMLResponse)
async def product_create_submit(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    product_type: str = Form(...),
    slug: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    strategy_id: str = Form(""),
    author_id: str = Form(""),
    bundle_id: str = Form(""),
    billing_period: str = Form(...),
    price_rub: str = Form(...),
    trial_days: str = Form("0"),
    is_active: str | None = Form(default=None),
    autorenew_allowed: str | None = Form(default=None),
) -> Response:
    try:
        data = _build_product_form_data(
            product_type=product_type,
            slug=slug,
            title=title,
            description=description,
            strategy_id=strategy_id,
            author_id=author_id,
            bundle_id=bundle_id,
            billing_period=billing_period,
            price_rub=price_rub,
            trial_days=trial_days,
            is_active=is_active,
            autorenew_allowed=autorenew_allowed,
        )
        product = await create_product(session, data)
    except ValueError as exc:
        return await _render_product_form(
            request=request,
            user=user,
            session=session,
            product=None,
            error=str(exc),
            form_values={
                "product_type": product_type,
                "slug": slug,
                "title": title,
                "description": description,
                "strategy_id": strategy_id,
                "author_id": author_id,
                "bundle_id": bundle_id,
                "billing_period": billing_period,
                "price_rub": price_rub,
                "trial_days": trial_days,
                "is_active": is_active is not None,
                "autorenew_allowed": autorenew_allowed is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/products/{product.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/products/{product_id}/edit", response_class=HTMLResponse)
async def product_edit_page(
    product_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    product = await get_admin_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return await _render_product_form(
        request=request,
        user=user,
        session=session,
        product=product,
        error=None,
        form_values=_form_values_from_product(product),
    )


@router.post("/products/{product_id}", response_class=HTMLResponse)
async def product_edit_submit(
    product_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    product_type: str = Form(...),
    slug: str = Form(...),
    title: str = Form(...),
    description: str = Form(""),
    strategy_id: str = Form(""),
    author_id: str = Form(""),
    bundle_id: str = Form(""),
    billing_period: str = Form(...),
    price_rub: str = Form(...),
    trial_days: str = Form("0"),
    is_active: str | None = Form(default=None),
    autorenew_allowed: str | None = Form(default=None),
) -> Response:
    product = await get_admin_product(session, product_id)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    try:
        data = _build_product_form_data(
            product_type=product_type,
            slug=slug,
            title=title,
            description=description,
            strategy_id=strategy_id,
            author_id=author_id,
            bundle_id=bundle_id,
            billing_period=billing_period,
            price_rub=price_rub,
            trial_days=trial_days,
            is_active=is_active,
            autorenew_allowed=autorenew_allowed,
        )
        await update_product(session, product, data)
    except ValueError as exc:
        return await _render_product_form(
            request=request,
            user=user,
            session=session,
            product=product,
            error=str(exc),
            form_values={
                "product_type": product_type,
                "slug": slug,
                "title": title,
                "description": description,
                "strategy_id": strategy_id,
                "author_id": author_id,
                "bundle_id": bundle_id,
                "billing_period": billing_period,
                "price_rub": price_rub,
                "trial_days": trial_days,
                "is_active": is_active is not None,
                "autorenew_allowed": autorenew_allowed is not None,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/products/{product.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/payments", response_class=HTMLResponse)
async def payment_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    payments = await list_admin_payments(session)
    review_stats = await get_payment_review_stats(session)
    return templates.TemplateResponse(
        request,
        "admin/payments_list.html",
        {
            "title": "Платежи",
            "user": user,
            "payments": payments,
            "review_stats": review_stats,
        },
    )


@router.get("/subscriptions", response_class=HTMLResponse)
async def subscription_list_page(
    request: Request,
    q: str = "",
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    subscriptions = await list_admin_subscriptions(session, query_text=q)
    stats = {
        "active": sum(1 for item in subscriptions if item.status.value == "active"),
        "trial": sum(1 for item in subscriptions if item.status.value == "trial"),
        "pending": sum(1 for item in subscriptions if item.status.value == "pending"),
        "paid": sum(1 for item in subscriptions if item.payment is not None and item.payment.status.value == "paid"),
    }
    return templates.TemplateResponse(
        request,
        "admin/subscriptions_list.html",
        {
            "title": "Подписки",
            "user": user,
            "subscriptions": subscriptions,
            "query_text": q,
            "stats": stats,
        },
    )


@router.get("/subscriptions/{subscription_id}", response_class=HTMLResponse)
async def subscription_detail_page(
    subscription_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    subscription = await get_admin_subscription(session, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return templates.TemplateResponse(
        request,
        "admin/subscription_detail.html",
        {
            "title": "Карточка подписки",
            "user": user,
            "subscription": subscription,
        },
    )


@router.get("/analytics/leads", response_class=HTMLResponse)
async def lead_analytics_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    rows = await list_lead_source_analytics(session)
    stats = {
        "sources": len(rows),
        "subscriptions": sum(item.subscriptions_total for item in rows),
        "revenue_rub": sum(item.revenue_rub for item in rows),
    }
    return templates.TemplateResponse(
        request,
        "admin/lead_analytics.html",
        {
            "title": "Lead source analytics",
            "user": user,
            "rows": rows,
            "stats": stats,
        },
    )


@router.get("/legal", response_class=HTMLResponse)
async def legal_document_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    documents = await list_admin_legal_documents(session)
    return templates.TemplateResponse(
        request,
        "admin/legal_list.html",
        {
            "title": "Юридические документы",
            "user": user,
            "documents": documents,
        },
    )


@router.get("/legal/new", response_class=HTMLResponse)
async def legal_document_create_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    return await _render_legal_form(
        request=request,
        user=user,
        session=session,
        document=None,
        error=None,
        form_values={},
    )


@router.post("/legal", response_class=HTMLResponse)
async def legal_document_create_submit(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    document_type: str = Form(...),
    version: str = Form(...),
    title: str = Form(...),
    content_md: str = Form(...),
) -> Response:
    try:
        data = _build_legal_form_data(
            document_type=document_type,
            version=version,
            title=title,
            content_md=content_md,
        )
        document = await create_admin_legal_document(session, data)
    except ValueError as exc:
        return await _render_legal_form(
            request=request,
            user=user,
            session=session,
            document=None,
            error=str(exc),
            form_values={
                "document_type": document_type,
                "version": version,
                "title": title,
                "content_md": content_md,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/legal/{document.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/legal/{document_id}/edit", response_class=HTMLResponse)
async def legal_document_edit_page(
    document_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    document = await get_admin_legal_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found")
    return await _render_legal_form(
        request=request,
        user=user,
        session=session,
        document=document,
        error=None,
        form_values=_form_values_from_legal_document(document),
    )


@router.post("/legal/{document_id}", response_class=HTMLResponse)
async def legal_document_edit_submit(
    document_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    document_type: str = Form(...),
    version: str = Form(...),
    title: str = Form(...),
    content_md: str = Form(...),
) -> Response:
    document = await get_admin_legal_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found")

    try:
        data = _build_legal_form_data(
            document_type=document_type,
            version=version,
            title=title,
            content_md=content_md,
        )
        await update_admin_legal_document(session, document, data)
    except ValueError as exc:
        return await _render_legal_form(
            request=request,
            user=user,
            session=session,
            document=document,
            error=str(exc),
            form_values={
                "document_type": document_type,
                "version": version,
                "title": title,
                "content_md": content_md,
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/legal/{document.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/legal/{document_id}/activate", response_class=HTMLResponse)
async def legal_document_activate_submit(
    document_id: str,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    document = await get_admin_legal_document(session, document_id)
    if document is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Legal document not found")
    await activate_admin_legal_document(session, document)
    return RedirectResponse(url=f"/admin/legal/{document.id}/edit", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/delivery", response_class=HTMLResponse)
async def delivery_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    records = await list_admin_delivery_records(session)
    stats = {
        "published": len(records),
        "delivered": sum(1 for item in records if item.latest_delivery_event is not None),
        "attempts": sum(item.delivery_attempts for item in records),
        "recipients": sum(item.delivered_recipients for item in records),
    }
    return templates.TemplateResponse(
        request,
        "admin/delivery_list.html",
        {
            "title": "Delivery operations",
            "user": user,
            "records": records,
            "stats": stats,
        },
    )


@router.get("/delivery/{recommendation_id}", response_class=HTMLResponse)
async def delivery_detail_page(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    record = await get_admin_delivery_record(session, recommendation_id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery record not found")
    return templates.TemplateResponse(
        request,
        "admin/delivery_detail.html",
        {
            "title": "Delivery detail",
            "user": user,
            "record": record,
            "error": None,
        },
    )


@router.post("/delivery/{recommendation_id}/retry", response_class=HTMLResponse)
async def delivery_retry_submit(
    recommendation_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    bot = create_bot(get_settings().telegram.bot_token.get_secret_value())
    try:
        try:
            record = await retry_recommendation_delivery(session, recommendation_id, bot)
        except ValueError as exc:
            current = await get_admin_delivery_record(session, recommendation_id)
            if current is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery record not found") from exc
            return templates.TemplateResponse(
                request,
                "admin/delivery_detail.html",
                {
                    "title": "Delivery detail",
                    "user": user,
                    "record": current,
                    "error": str(exc),
                },
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            )
    finally:
        await bot.session.close()
    return RedirectResponse(
        url=f"/admin/delivery/{record.recommendation.id}",
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/payments/{payment_id}", response_class=HTMLResponse)
async def payment_detail_page(
    payment_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    payment = await get_admin_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return templates.TemplateResponse(
        request,
        "admin/payment_detail.html",
        {
            "title": "Проверка платежа",
            "user": user,
            "payment": payment,
            "error": None,
        },
    )


@router.post("/payments/{payment_id}/confirm", response_class=HTMLResponse)
async def payment_confirm_submit(
    payment_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    payment = await get_admin_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    try:
        await confirm_payment_and_activate_subscription(session, payment)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/payment_detail.html",
            {
                "title": "Проверка платежа",
                "user": user,
                "payment": payment,
                "error": str(exc),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/payments/{payment.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/payments/{payment_id}/manual-discount", response_class=HTMLResponse)
async def payment_manual_discount_submit(
    payment_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    discount_rub: str = Form("0"),
) -> Response:
    payment = await get_admin_payment(session, payment_id)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    try:
        parsed_discount = int(discount_rub.strip() or "0")
        await apply_manual_discount_to_payment(session, payment, discount_rub=parsed_discount)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/payment_detail.html",
            {
                "title": "Проверка платежа",
                "user": user,
                "payment": payment,
                "error": str(exc),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/payments/{payment.id}", status_code=status.HTTP_303_SEE_OTHER)


async def _render_strategy_form(
    request: Request,
    user: User,
    session: AsyncSession | None,
    strategy,
    error: str | None,
    form_values: dict[str, object],
    status_code: int = status.HTTP_200_OK,
) -> Response:
    authors = await list_admin_authors(session)
    return templates.TemplateResponse(
        request,
        "admin/strategy_form.html",
        {
            "title": "Карточка стратегии" if strategy is not None else "Новая стратегия",
            "user": user,
            "strategy": strategy,
            "authors": authors,
            "error": error,
            "form_values": form_values,
            "risk_levels": list(RiskLevel),
            "strategy_statuses": list(StrategyStatus),
        },
        status_code=status_code,
    )


async def _render_product_form(
    request: Request,
    user: User,
    session: AsyncSession | None,
    product,
    error: str | None,
    form_values: dict[str, object],
    status_code: int = status.HTTP_200_OK,
) -> Response:
    authors = await list_admin_authors(session)
    strategies = await list_admin_strategies(session)
    bundles = await list_admin_bundles(session)
    return templates.TemplateResponse(
        request,
        "admin/product_form.html",
        {
            "title": "Продукт подписки" if product is not None else "Новый продукт подписки",
            "user": user,
            "product": product,
            "authors": authors,
            "strategies": strategies,
            "bundles": bundles,
            "error": error,
            "form_values": form_values,
            "product_types": list(ProductType),
            "billing_periods": list(BillingPeriod),
        },
        status_code=status_code,
    )


async def _render_legal_form(
    request: Request,
    user: User,
    session: AsyncSession | None,
    document,
    error: str | None,
    form_values: dict[str, object],
    status_code: int = status.HTTP_200_OK,
) -> Response:
    documents = await list_admin_legal_documents(session)
    return templates.TemplateResponse(
        request,
        "admin/legal_form.html",
        {
            "title": "Юридический документ" if document is not None else "Новый юридический документ",
            "user": user,
            "document": document,
            "documents": documents,
            "error": error,
            "form_values": form_values,
            "document_types": list(LegalDocumentType),
        },
        status_code=status_code,
    )


async def _render_promo_form(
    request: Request,
    user: User,
    session: AsyncSession | None,
    promo_code,
    error: str | None,
    form_values: dict[str, object],
    status_code: int = status.HTTP_200_OK,
) -> Response:
    promo_codes = await list_admin_promo_codes(session)
    return templates.TemplateResponse(
        request,
        "admin/promo_form.html",
        {
            "title": "Промокод" if promo_code is not None else "Новый промокод",
            "user": user,
            "promo_code": promo_code,
            "promo_codes": promo_codes,
            "error": error,
            "form_values": form_values,
        },
        status_code=status_code,
    )


def _build_strategy_form_data(
    *,
    author_id: str,
    slug: str,
    title: str,
    short_description: str,
    full_description: str,
    risk_level: str,
    status_value: str,
    min_capital_rub: str,
    is_public: str | None,
) -> StrategyFormData:
    if not author_id.strip():
        raise ValueError("Автор обязателен")
    normalized_slug = slug.strip().lower()
    if not normalized_slug:
        raise ValueError("Slug обязателен")
    if not title.strip():
        raise ValueError("Название стратегии обязательно")
    if not short_description.strip():
        raise ValueError("Короткое описание обязательно")

    capital_value = min_capital_rub.strip()
    parsed_capital = int(capital_value) if capital_value else None
    return StrategyFormData(
        author_id=author_id.strip(),
        slug=normalized_slug,
        title=title.strip(),
        short_description=short_description.strip(),
        full_description=full_description.strip() or None,
        risk_level=RiskLevel(risk_level),
        status=StrategyStatus(status_value),
        min_capital_rub=parsed_capital,
        is_public=is_public is not None,
    )


def _form_values_from_strategy(strategy) -> dict[str, object]:
    return {
        "author_id": strategy.author_id,
        "slug": strategy.slug,
        "title": strategy.title,
        "short_description": strategy.short_description,
        "full_description": strategy.full_description or "",
        "risk_level": strategy.risk_level.value,
        "status": strategy.status.value,
        "min_capital_rub": strategy.min_capital_rub or "",
        "is_public": strategy.is_public,
    }


def _form_values_from_promo_code(promo_code) -> dict[str, object]:
    return {
        "code": promo_code.code,
        "description": promo_code.description or "",
        "discount_percent": promo_code.discount_percent or "",
        "discount_amount_rub": promo_code.discount_amount_rub or "",
        "max_redemptions": promo_code.max_redemptions or "",
        "expires_at": promo_code.expires_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")
        if promo_code.expires_at is not None
        else "",
        "is_active": promo_code.is_active,
    }


def _build_product_form_data(
    *,
    product_type: str,
    slug: str,
    title: str,
    description: str,
    strategy_id: str,
    author_id: str,
    bundle_id: str,
    billing_period: str,
    price_rub: str,
    trial_days: str,
    is_active: str | None,
    autorenew_allowed: str | None,
) -> ProductFormData:
    normalized_slug = slug.strip().lower()
    if not normalized_slug:
        raise ValueError("Slug обязателен")
    if not title.strip():
        raise ValueError("Название продукта обязательно")

    parsed_type = ProductType(product_type)
    strategy_value = strategy_id.strip() or None
    author_value = author_id.strip() or None
    bundle_value = bundle_id.strip() or None

    if parsed_type is ProductType.STRATEGY:
        if strategy_value is None:
            raise ValueError("Для strategy-продукта нужно выбрать стратегию")
        author_value = None
        bundle_value = None
    elif parsed_type is ProductType.AUTHOR:
        if author_value is None:
            raise ValueError("Для author-продукта нужно выбрать автора")
        strategy_value = None
        bundle_value = None
    else:
        if bundle_value is None:
            raise ValueError("Для bundle-продукта нужно выбрать bundle")
        strategy_value = None
        author_value = None

    try:
        parsed_price = int(price_rub.strip())
    except ValueError as exc:
        raise ValueError("Цена должна быть целым числом") from exc
    try:
        parsed_trial = int((trial_days or "0").strip())
    except ValueError as exc:
        raise ValueError("Trial days должен быть целым числом") from exc

    if parsed_price < 0:
        raise ValueError("Цена не может быть отрицательной")
    if parsed_trial < 0:
        raise ValueError("Trial days не может быть отрицательным")

    return ProductFormData(
        product_type=parsed_type,
        slug=normalized_slug,
        title=title.strip(),
        description=description.strip() or None,
        strategy_id=strategy_value,
        author_id=author_value,
        bundle_id=bundle_value,
        billing_period=BillingPeriod(billing_period),
        price_rub=parsed_price,
        trial_days=parsed_trial,
        is_active=is_active is not None,
        autorenew_allowed=autorenew_allowed is not None,
    )


def _build_promo_form_data(
    *,
    code: str,
    description: str,
    discount_percent: str,
    discount_amount_rub: str,
    max_redemptions: str,
    expires_at: str,
    is_active: str | None,
) -> PromoCodeFormData:
    normalized_code = code.strip().upper()
    if not normalized_code:
        raise ValueError("Код промокода обязателен")

    percent_value = discount_percent.strip()
    amount_value = discount_amount_rub.strip()
    max_value = max_redemptions.strip()
    expires_value = expires_at.strip()

    parsed_percent = int(percent_value) if percent_value else None
    parsed_amount = int(amount_value) if amount_value else None
    parsed_max = int(max_value) if max_value else None
    parsed_expires_at = datetime.fromisoformat(expires_value) if expires_value else None
    if parsed_expires_at is not None and parsed_expires_at.tzinfo is None:
        parsed_expires_at = parsed_expires_at.replace(tzinfo=UTC)

    if parsed_percent is None and parsed_amount is None:
        raise ValueError("Нужно указать discount percent или fixed amount")
    if parsed_percent is not None and parsed_amount is not None:
        raise ValueError("Используйте либо discount percent, либо fixed amount")
    if parsed_percent is not None and not (1 <= parsed_percent <= 100):
        raise ValueError("Discount percent должен быть в диапазоне 1..100")
    if parsed_amount is not None and parsed_amount < 0:
        raise ValueError("Discount amount не может быть отрицательным")
    if parsed_max is not None and parsed_max <= 0:
        raise ValueError("Лимит использований должен быть больше нуля")

    return PromoCodeFormData(
        code=normalized_code,
        description=description.strip() or None,
        discount_percent=parsed_percent,
        discount_amount_rub=parsed_amount,
        max_redemptions=parsed_max,
        expires_at=parsed_expires_at,
        is_active=is_active is not None,
    )


def _form_values_from_product(product) -> dict[str, object]:
    return {
        "product_type": product.product_type.value,
        "slug": product.slug,
        "title": product.title,
        "description": product.description or "",
        "strategy_id": product.strategy_id or "",
        "author_id": product.author_id or "",
        "bundle_id": product.bundle_id or "",
        "billing_period": product.billing_period.value,
        "price_rub": product.price_rub,
        "trial_days": product.trial_days,
        "is_active": product.is_active,
        "autorenew_allowed": product.autorenew_allowed,
    }


def _build_legal_form_data(
    *,
    document_type: str,
    version: str,
    title: str,
    content_md: str,
) -> LegalDocumentFormData:
    normalized_version = version.strip()
    if not normalized_version:
        raise ValueError("Версия документа обязательна")
    if not title.strip():
        raise ValueError("Название документа обязательно")
    if not content_md.strip():
        raise ValueError("Markdown содержимое обязательно")
    return LegalDocumentFormData(
        document_type=LegalDocumentType(document_type),
        version=normalized_version,
        title=title.strip(),
        content_md=content_md.strip(),
    )


def _form_values_from_legal_document(document) -> dict[str, object]:
    return {
        "document_type": document.document_type.value,
        "version": document.version,
        "title": document.title,
        "content_md": read_legal_document_markdown(document),
    }
