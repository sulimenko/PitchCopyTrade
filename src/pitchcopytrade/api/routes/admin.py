from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.api.deps.auth import require_admin
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import BillingPeriod, ProductType, RiskLevel, StrategyStatus
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.services.admin import (
    ProductFormData,
    confirm_payment_and_activate_subscription,
    StrategyFormData,
    create_product,
    create_strategy,
    get_admin_payment,
    get_admin_product,
    get_admin_dashboard_stats,
    get_payment_review_stats,
    get_admin_strategy,
    list_admin_authors,
    list_admin_bundles,
    list_admin_payments,
    list_admin_products,
    list_admin_strategies,
    update_product,
    update_strategy,
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
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    stats = await get_admin_dashboard_stats(session)
    strategies = await list_admin_strategies(session)
    products = await list_admin_products(session)
    payments = await list_admin_payments(session)
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
        },
    )


@router.get("/strategies", response_class=HTMLResponse)
async def strategy_list_page(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    return await _render_product_form(
        request=request,
        user=user,
        session=session,
        product=None,
        error=None,
        form_values={},
    )


@router.post("/products", response_class=HTMLResponse)
async def product_create_submit(
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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


@router.get("/payments/{payment_id}", response_class=HTMLResponse)
async def payment_detail_page(
    payment_id: str,
    request: Request,
    user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db_session),
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
    session: AsyncSession = Depends(get_db_session),
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


async def _render_strategy_form(
    request: Request,
    user: User,
    session: AsyncSession,
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
    session: AsyncSession,
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
