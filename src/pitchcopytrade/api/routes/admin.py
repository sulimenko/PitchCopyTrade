from __future__ import annotations

from datetime import UTC, datetime
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import require_admin
from pitchcopytrade.auth.session import build_staff_invite_link
from pitchcopytrade.bot.main import create_bot
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import BillingPeriod, LegalDocumentType, ProductType, RiskLevel, RoleSlug, StrategyStatus
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.services.admin import (
    AdminAuthorUpdateData,
    ProductFormData,
    StaffUpdateData,
    apply_manual_discount_to_payment,
    cancel_subscription_admin,
    confirm_payment_and_activate_subscription,
    create_admin_author,
    create_admin_staff_user,
    get_admin_metrics,
    get_admin_strategy_for_onepager,
    grant_staff_role,
    list_admin_staff,
    reseed_author_watchlists,
    set_subscription_autorenew_admin,
    revoke_staff_role,
    save_strategy_onepager,
    toggle_admin_author,
    StaffCreateData,
    StrategyFormData,
    update_admin_author_permissions,
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
    resend_staff_invite,
    set_admin_staff_user_status,
    update_admin_author,
    update_admin_staff_user,
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
from pitchcopytrade.api.routes._grid_serializers import (
    serialize_strategies,
    serialize_authors,
    serialize_staff,
    serialize_products,
    serialize_subscriptions,
    serialize_payments,
    serialize_legal,
    serialize_promos,
    serialize_delivery,
    serialize_lead_analytics,
    serialize_metrics_strategies,
)


router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)


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
            "authors_url": "/admin/authors",
        },
    )


@router.get("/strategies", response_class=HTMLResponse)
async def strategy_list_page(
    request: Request,
    q: str = "",
    sort_by: str = "title",
    direction: str = "asc",
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    strategies = await list_admin_strategies(session)
    strategies = _filter_admin_strategies(strategies, q=q)
    strategies = _sort_admin_strategies(strategies, sort_by=sort_by, direction=direction)
    return templates.TemplateResponse(
        request,
        "admin/strategies_list.html",
        {
            "title": "Стратегии",
            "user": user,
            "strategies": strategies,
            "strategies_json": serialize_strategies(strategies),
            "q": q,
            "sort_by": sort_by,
            "direction": direction,
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
    strategy_id = _validate_uuid(strategy_id)  # Z6: Validate UUID
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
    strategy_id = _validate_uuid(strategy_id)  # Z6: Validate UUID
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
            "products_json": serialize_products(products),
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
            "promos_json": serialize_promos(promo_codes),
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
    promo_code_id = _validate_uuid(promo_code_id)  # Z6: Validate UUID
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
    promo_code_id = _validate_uuid(promo_code_id)  # Z6: Validate UUID
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
    product_id = _validate_uuid(product_id)  # Z6: Validate UUID
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
    product_id = _validate_uuid(product_id)  # Z6: Validate UUID
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
            "payments_json": serialize_payments(payments),
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
            "subscriptions_json": serialize_subscriptions(subscriptions),
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
            "error": None,
        },
    )


@router.post("/subscriptions/{subscription_id}/autorenew/disable", response_class=HTMLResponse)
async def subscription_disable_autorenew_submit(
    subscription_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    subscription = await get_admin_subscription(session, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    try:
        await set_subscription_autorenew_admin(session, subscription, enabled=False)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/subscription_detail.html",
            {
                "title": "Карточка подписки",
                "user": user,
                "subscription": subscription,
                "error": str(exc),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/subscriptions/{subscription.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/subscriptions/{subscription_id}/cancel", response_class=HTMLResponse)
async def subscription_cancel_submit(
    subscription_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    subscription = await get_admin_subscription(session, subscription_id)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    try:
        await cancel_subscription_admin(session, subscription)
    except ValueError as exc:
        return templates.TemplateResponse(
            request,
            "admin/subscription_detail.html",
            {
                "title": "Карточка подписки",
                "user": user,
                "subscription": subscription,
                "error": str(exc),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url=f"/admin/subscriptions/{subscription.id}", status_code=status.HTTP_303_SEE_OTHER)


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
            "analytics_json": serialize_lead_analytics(rows),
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
            "legal_json": serialize_legal(documents),
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
    document_id = _validate_uuid(document_id)  # Z6: Validate UUID
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
    document_id = _validate_uuid(document_id)  # Z6: Validate UUID
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
    document_id = _validate_uuid(document_id)  # Z6: Validate UUID
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
            "delivery_json": serialize_delivery(records),
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


def _validate_uuid(value: str) -> str:
    """Z6: Validate UUID path parameter to prevent non-UUID values (like 'new') from causing DataError.
    Raises 404 for invalid UUIDs instead of 500 from SQLAlchemy."""
    try:
        UUID(value)
        return value
    except (ValueError, AttributeError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")


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


@router.get("/authors", response_class=HTMLResponse)
async def admin_authors_list(
    request: Request,
    status_filter: str = "all",
    q: str = "",
    sort_by: str = "display_name",
    direction: str = "asc",
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    return await _render_admin_authors_registry(
        request=request,
        user=user,
        session=session,
        status_filter=status_filter,
        q=q,
        sort_by=sort_by,
        direction=direction,
    )


@router.post("/authors", response_class=HTMLResponse)
async def admin_author_create(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    display_name: str = Form(...),
    email: str = Form(""),
    telegram_user_id: str = Form(""),
) -> Response:
    try:
        tg_id = int(telegram_user_id.strip()) if telegram_user_id.strip() else None
        await create_admin_author(
            session,
            display_name=display_name.strip(),
            email=email.strip() or None,
            telegram_user_id=tg_id,
        )
    except ValueError as exc:
        return await _render_admin_authors_registry(
            request=request,
            user=user,
            session=session,
            error=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/authors", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/authors/{author_id}/edit", response_class=HTMLResponse)
async def admin_author_edit(
    author_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    display_name: str = Form(...),
    email: str = Form(""),
    telegram_user_id: str = Form(""),
    role_slugs: list[str] | None = Form(default=None),
    requires_moderation: str | None = Form(default=None),
    status_value: str = Form("active"),
) -> Response:
    try:
        tg_id = int(telegram_user_id.strip()) if telegram_user_id.strip() else None
        await update_admin_author(
            session,
            actor_user_id=user.id,
            author_id=author_id,
            data=AdminAuthorUpdateData(
                display_name=display_name.strip(),
                email=email.strip() or None,
                telegram_user_id=tg_id,
                role_slugs=tuple(RoleSlug(value) for value in (role_slugs or [RoleSlug.AUTHOR.value])),
                requires_moderation=requires_moderation is not None,
                is_active=status_value == "active",
            ),
        )
    except ValueError as exc:
        return await _render_admin_authors_registry(
            request=request,
            user=user,
            session=session,
            error=str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/authors", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/staff", response_class=HTMLResponse)
async def admin_staff_list(
    request: Request,
    role_filter: str = "all",
    q: str = "",
    sort_by: str = "display_name",
    direction: str = "asc",
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    staff = await list_admin_staff(session, role_filter=role_filter)
    staff = _filter_admin_staff_rows(staff, q=q)
    staff = _sort_admin_staff_rows(staff, sort_by=sort_by, direction=direction)
    staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
    return templates.TemplateResponse(
        request,
        "admin/staff_list.html",
        {
            "title": "Команда",
            "user": user,
            "staff": staff_rows,
            "staff_json": serialize_staff(staff_rows, user.id),
            "current_user_id": user.id,
            "role_filter": role_filter,
            "q": q,
            "sort_by": sort_by,
            "direction": direction,
        },
    )


@router.post("/staff/admins", response_class=HTMLResponse)
async def admin_staff_create_admin(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    display_name: str = Form(...),
    email: str = Form(""),
    telegram_user_id: str = Form(""),
) -> Response:
    try:
        tg_id = int(telegram_user_id.strip()) if telegram_user_id.strip() else None
        await create_admin_staff_user(
            session,
            StaffCreateData(
                display_name=display_name.strip(),
                email=email.strip() or None,
                telegram_user_id=tg_id,
                role_slugs=(RoleSlug.ADMIN,),
            ),
        )
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/edit", response_class=HTMLResponse)
async def admin_staff_edit(
    target_user_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    display_name: str = Form(...),
    email: str = Form(""),
    telegram_user_id: str = Form(""),
    role_slugs: list[str] | None = Form(default=None),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        tg_id = int(telegram_user_id.strip()) if telegram_user_id.strip() else None
        await update_admin_staff_user(
            session,
            actor_user_id=user.id,
            user_id=target_user_id,
            data=StaffUpdateData(
                display_name=display_name.strip(),
                email=email.strip() or None,
                telegram_user_id=tg_id,
                role_slugs=tuple(RoleSlug(value) for value in (role_slugs or [])),
            ),
        )
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/roles", response_class=HTMLResponse)
async def admin_staff_grant_role(
    target_user_id: str,
    request: Request,
    role_slug: str = Form(...),
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        await grant_staff_role(
            session,
            actor_user_id=user.id,
            target_user_id=target_user_id,
            role_slug=RoleSlug(role_slug),
        )
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/roles/{role_slug}/remove", response_class=HTMLResponse)
async def admin_staff_revoke_role(
    target_user_id: str,
    role_slug: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        await revoke_staff_role(
            session,
            actor_user_id=user.id,
            target_user_id=target_user_id,
            role_slug=RoleSlug(role_slug),
        )
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/activate", response_class=HTMLResponse)
async def admin_staff_activate(
    target_user_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        await set_admin_staff_user_status(session, actor_user_id=user.id, user_id=target_user_id, is_active=True)
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/deactivate", response_class=HTMLResponse)
async def admin_staff_deactivate(
    target_user_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        await set_admin_staff_user_status(session, actor_user_id=user.id, user_id=target_user_id, is_active=False)
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/staff/{target_user_id}/invite/resend", response_class=HTMLResponse)
async def admin_staff_resend_invite(
    target_user_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    target_user_id = _validate_uuid(target_user_id)  # Z6: Validate UUID
    try:
        await resend_staff_invite(session, user_id=target_user_id)
    except ValueError as exc:
        staff = await list_admin_staff(session)
        staff_rows = [_staff_row(item, current_user_id=user.id) for item in staff]
        return templates.TemplateResponse(
            request,
            "admin/staff_list.html",
            {
                "title": "Команда",
                "user": user,
                "staff": staff_rows,
                "error": str(exc),
                "role_filter": "all",
                "q": "",
                "sort_by": "display_name",
                "direction": "asc",
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
    return RedirectResponse(url="/admin/staff", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/authors/{author_id}/permissions", response_class=HTMLResponse)
async def admin_author_permissions_update(
    author_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    requires_moderation: str | None = Form(default=None),
) -> Response:
    try:
        await update_admin_author_permissions(
            session,
            author_id,
            requires_moderation=requires_moderation is not None,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Автор не найден")
    return RedirectResponse(url="/admin/authors", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/authors/reseed-watchlist", response_class=HTMLResponse)
async def admin_authors_reseed_watchlist(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    updated = await reseed_author_watchlists(session)
    return RedirectResponse(url=f"/admin/authors?reseed={updated}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/authors/{author_id}/toggle", response_class=HTMLResponse)
async def admin_author_toggle(
    author_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    try:
        await toggle_admin_author(session, author_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Автор не найден")
    return RedirectResponse(url="/admin/authors", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/onepager/{strategy_id}", response_class=HTMLResponse)
async def admin_onepager_edit(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    strategy_id = _validate_uuid(strategy_id)  # Z6: Validate UUID
    strategy = await get_admin_strategy_for_onepager(session, strategy_id)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    return templates.TemplateResponse(
        request,
        "admin/onepager.html",
        {"title": "One Pager", "user": user, "strategy": strategy},
    )


@router.post("/onepager/{strategy_id}", response_class=HTMLResponse)
async def admin_onepager_save(
    strategy_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
    html_content: str = Form(""),
) -> Response:
    strategy_id = _validate_uuid(strategy_id)  # Z6: Validate UUID
    try:
        await save_strategy_onepager(session, strategy_id, html_content)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Стратегия не найдена")
    return RedirectResponse(url=f"/admin/onepager/{strategy_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/metrics", response_class=HTMLResponse)
async def admin_metrics(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession | None = Depends(get_optional_db_session),
) -> Response:
    metrics = await get_admin_metrics(session)
    return templates.TemplateResponse(
        request,
        "admin/metrics.html",
        {"title": "Метрики", "user": user, "metrics": metrics, "metrics_json": serialize_metrics_strategies(metrics)},
    )


def _author_row(author) -> dict[str, object]:
    user = getattr(author, "user", None)
    role_slugs = _safe_role_slugs(user)
    display_name = (
        getattr(author, "display_name", None)
        or getattr(author, "slug", None)
        or getattr(user, "full_name", None)
        or getattr(user, "email", None)
        or getattr(user, "username", None)
        or getattr(author, "id", None)
        or "Автор без имени"
    )
    email = getattr(user, "email", None) if user is not None else None
    telegram_user_id = getattr(user, "telegram_user_id", None) if user is not None else None
    invite_delivery_status = getattr(user, "invite_delivery_status", None) if user is not None else None
    invite_delivery_error = getattr(user, "invite_delivery_error", None) if user is not None else None
    invite_delivery_updated_at = getattr(user, "invite_delivery_updated_at", None) if user is not None else None
    user_id = getattr(user, "id", None) if user is not None else None
    invite_link = None
    if user is not None and user_id and telegram_user_id is None:
        invite_link = build_staff_invite_link(user)
    known_roles = {"admin", "author", "moderator"}
    return {
        "id": getattr(author, "id", ""),
        "display_name": display_name,
        "slug": getattr(author, "slug", "") or "",
        "email": email or "",
        "telegram_user_id": telegram_user_id,
        "user_id": user_id,
        "has_linked_user": user is not None and bool(user_id),
        "user_warning": None if user is not None else "Связанный staff-аккаунт не найден.",
        "is_active": bool(getattr(author, "is_active", False)),
        "invite_link": invite_link,
        "invite_delivery_status": invite_delivery_status,
        "invite_delivery_error": invite_delivery_error,
        "invite_delivery_updated_at": invite_delivery_updated_at,
        "requires_moderation": bool(getattr(author, "requires_moderation", False)),
        "status": "active" if getattr(author, "is_active", False) else "inactive",
        "roles": role_slugs,
        "extra_roles": [item for item in role_slugs if item not in known_roles],
        "has_admin_role": "admin" in role_slugs,
        "has_author_role": "author" in role_slugs,
        "has_moderator_role": "moderator" in role_slugs,
    }


def _staff_row(user: User, *, current_user_id: str) -> dict[str, object]:
    role_order = {"admin": 0, "author": 1, "moderator": 2}
    role_slugs = sorted((item.slug.value for item in user.roles), key=lambda item: (role_order.get(item, 99), item))
    invite_link = None
    if user.telegram_user_id is None:
        invite_link = build_staff_invite_link(user)
    status_value = user.status.value if getattr(user, "status", None) is not None else "active"
    return {
        "id": user.id,
        "display_name": user.author_profile.display_name if user.author_profile is not None else (user.full_name or user.email or user.username),
        "email": user.email,
        "telegram_user_id": user.telegram_user_id,
        "status": status_value,
        "invite_delivery_status": user.invite_delivery_status.value if getattr(user, "invite_delivery_status", None) is not None else None,
        "invite_delivery_error": getattr(user, "invite_delivery_error", None),
        "invite_delivery_updated_at": getattr(user, "invite_delivery_updated_at", None),
        "invite_link": invite_link,
        "roles": role_slugs,
        "has_admin_role": "admin" in role_slugs,
        "has_author_role": "author" in role_slugs,
        "has_moderator_role": "moderator" in role_slugs,
        "is_multi_role": len(role_slugs) > 1,
        "can_grant_admin": "admin" not in role_slugs,
        "can_grant_author": "author" not in role_slugs,
        "can_revoke_admin": "admin" in role_slugs,
        "is_current_user": user.id == current_user_id,
    }


def _filter_admin_author_rows(authors, *, q: str):
    normalized = q.strip().lower()
    if not normalized:
        return authors
    return [
        item for item in authors
        if normalized in " ".join(
            part.lower()
            for part in [
                getattr(item, "display_name", None) or "",
                getattr(item, "slug", None) or "",
                getattr(getattr(item, "user", None), "email", None) or "",
                " ".join(_safe_role_slugs(getattr(item, "user", None))),
            ]
            if part
        )
    ]


def _sort_admin_author_rows(authors, *, sort_by: str, direction: str):
    reverse = direction == "desc"
    if sort_by == "status":
        key = lambda item: "active" if getattr(item, "is_active", False) else "inactive"
    elif sort_by == "moderation":
        key = lambda item: "review" if getattr(item, "requires_moderation", False) else "direct"
    else:
        key = lambda item: ((getattr(item, "display_name", None) or getattr(item, "slug", None) or getattr(item, "id", None) or "")).lower()
    return sorted(authors, key=key, reverse=reverse)


async def _render_admin_authors_registry(
    *,
    request: Request,
    user: User,
    session: AsyncSession | None,
    status_filter: str = "all",
    q: str = "",
    sort_by: str = "display_name",
    direction: str = "asc",
    error: str | None = None,
    status_code: int = status.HTTP_200_OK,
) -> Response:
    template_error = error
    try:
        authors = await list_admin_authors(session, status_filter=status_filter)
        authors = _filter_admin_author_rows(authors, q=q)
        authors = _sort_admin_author_rows(authors, sort_by=sort_by, direction=direction)
        author_rows: list[dict[str, object]] = []
        skipped_rows = 0
        for author in authors:
            try:
                author_rows.append(_author_row(author))
            except Exception:
                skipped_rows += 1
                logger.exception("admin author row build failed for %s", getattr(author, "id", None))
        if skipped_rows:
            warning = f"Часть строк реестра авторов пропущена: {skipped_rows}. Проверьте связанные staff/user данные."
            template_error = f"{template_error} {warning}".strip() if template_error else warning
    except Exception:
        logger.exception("admin authors registry failed")
        author_rows = []
        fallback = "Не удалось загрузить реестр авторов. Проверьте связанные staff/user данные и повторите попытку."
        template_error = f"{template_error} {fallback}".strip() if template_error else fallback

    return templates.TemplateResponse(
        request,
        "admin/authors_list.html",
        {
            "title": "Авторы",
            "user": user,
            "authors": author_rows,
            "authors_json": serialize_authors(author_rows),
            "current_user_id": user.id,
            "error": template_error,
            "status_filter": status_filter,
            "q": q,
            "sort_by": sort_by,
            "direction": direction,
        },
        status_code=status_code,
    )


def _safe_role_slugs(user: User | None) -> list[str]:
    role_order = {"admin": 0, "author": 1, "moderator": 2}
    if user is None:
        return []
    normalized: list[str] = []
    for item in getattr(user, "roles", None) or []:
        slug = getattr(item, "slug", None)
        value = getattr(slug, "value", slug)
        if value:
            normalized.append(str(value))
    return sorted(set(normalized), key=lambda item: (role_order.get(item, 99), item))


def _filter_admin_staff_rows(users, *, q: str):
    normalized = q.strip().lower()
    if not normalized:
        return users
    return [
        item for item in users
        if normalized in " ".join(
            part.lower()
            for part in [
                item.full_name or "",
                item.email or "",
                item.username or "",
                item.author_profile.display_name if item.author_profile is not None else "",
                " ".join(role.slug.value for role in item.roles),
            ]
            if part
        )
    ]


def _sort_admin_staff_rows(users, *, sort_by: str, direction: str):
    reverse = direction == "desc"
    if sort_by == "status":
        key = lambda item: item.status.value if item.status is not None else "active"
    elif sort_by == "roles":
        key = lambda item: ",".join(sorted(role.slug.value for role in item.roles))
    else:
        key = lambda item: (item.author_profile.display_name if item.author_profile is not None else (item.full_name or item.email or item.username or "")).lower()
    return sorted(users, key=key, reverse=reverse)


def _filter_admin_strategies(strategies, *, q: str):
    normalized = q.strip().lower()
    if not normalized:
        return strategies
    return [
        item
        for item in strategies
        if normalized in " ".join(
            part.lower()
            for part in [
                item.title,
                item.slug,
                item.short_description or "",
                item.author.display_name if item.author is not None else "",
                item.status.value,
                item.risk_level.value,
            ]
            if part
        )
    ]


def _sort_admin_strategies(strategies, *, sort_by: str, direction: str):
    reverse = direction == "desc"
    if sort_by == "status":
        key = lambda item: item.status.value
    elif sort_by == "risk":
        key = lambda item: item.risk_level.value
    elif sort_by == "author":
        key = lambda item: item.author.display_name.lower() if item.author is not None else ""
    else:
        key = lambda item: item.title.lower()
    return sorted(strategies, key=key, reverse=reverse)
