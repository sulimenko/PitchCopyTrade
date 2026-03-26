from __future__ import annotations

from types import SimpleNamespace

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.services.subscriber import (
    billing_period_label,
    build_action_cards,
    payment_history,
    payment_result_message,
    payment_status_label,
    subscription_status_label,
    subscription_renewal_history,
)
from pitchcopytrade.services.preview import (
    build_preview_admin_context,
    build_preview_author_context,
    build_preview_miniapp_context,
    build_preview_recommendation_context,
)
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/preview", tags=["preview"])


def _preview_disabled() -> Response:
    return Response(status_code=status.HTTP_404_NOT_FOUND)


def _rewrite_preview_href(href: str) -> str:
    if href.startswith("/app/"):
        return href.replace("/app/", "/preview/app/", 1)
    return href


@router.get("", include_in_schema=False)
async def preview_root(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "preview/index.html",
        {
            "title": "Preview mode",
            "preview_mode": True,
        },
    )


@router.get("/app", include_in_schema=False)
async def preview_app_root() -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url="/preview/app/catalog", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/catalog", response_class=HTMLResponse)
async def preview_app_catalog(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    strategy = preview["preview_strategy"]
    snapshot = preview["preview_snapshot"]
    return templates.TemplateResponse(
        request,
        "public/catalog.html",
        {
            "title": "Каталог Mini App preview",
            "strategies": [strategy],
            "telegram_bot_username": "preview_bot",
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
        },
    )


@router.get("/app/strategies/{slug}", response_class=HTMLResponse)
async def preview_app_strategy_detail(slug: str, request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    strategy = preview["preview_strategy"]
    if slug != strategy.slug:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "public/strategy_detail.html",
        {
            "title": strategy.title,
            "strategy": strategy,
            "miniapp_mode": True,
            "preview_mode": True,
        },
    )


@router.get("/app/checkout/{product_id}", response_class=HTMLResponse)
async def preview_app_checkout_page(product_id: str, request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    product = preview["preview_product"]
    if product_id != product.id:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "public/checkout.html",
        {
            "title": f"Подписка {product.title}",
            "product": product,
            "documents": [],
            "checkout_ready": True,
            "payment_provider": "stub_manual",
            "miniapp_mode": True,
            "preview_mode": True,
            "error": None,
            "form_values": {
                "full_name": preview["preview_user"].full_name,
                "email": "preview@example.com",
                "timezone_name": "Europe/Moscow",
                "lead_source_name": "telegram_miniapp",
                "promo_code_value": "",
                "accepted_document_ids": [],
            },
        },
    )


@router.post("/app/checkout/{product_id}", response_class=HTMLResponse)
async def preview_app_checkout_submit(
    product_id: str,
    request: Request,
    full_name: str = Form(""),
    email: str = Form(""),
    timezone_name: str = Form("Europe/Moscow"),
    promo_code_value: str = Form(""),
) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    product = preview["preview_product"]
    if product_id != product.id:
        return _preview_disabled()
    payment = preview["preview_snapshot"].payments[0]
    subscription = preview["preview_snapshot"].subscriptions[0]
    result = SimpleNamespace(
        payment=payment,
        subscription=subscription,
        user=preview["preview_user"],
        payment_url=None,
        applied_promo_code=None,
    )
    return templates.TemplateResponse(
        request,
        "public/checkout_success.html",
        {
            "title": "Заявка создана",
            "product": product,
            "result": result,
            "payment_provider": "stub_manual",
            "miniapp_mode": True,
            "preview_mode": True,
        },
    )


@router.get("/app/status", response_class=HTMLResponse)
async def preview_app_status(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    snapshot = preview["preview_snapshot"]
    action_cards = build_action_cards(snapshot)
    for card in action_cards:
        card.href = _rewrite_preview_href(card.href)
    return templates.TemplateResponse(
        request,
        "app/status.html",
        {
            "title": "Статус подписки preview",
            "user": preview["preview_user"],
            "snapshot": snapshot,
            "action_cards": action_cards,
            "payment_status_label": payment_status_label,
            "subscription_status_label": subscription_status_label,
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
            "miniapp_active": "status",
        },
    )


@router.get("/app/payments", response_class=HTMLResponse)
async def preview_app_payments(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    snapshot = preview["preview_snapshot"]
    return templates.TemplateResponse(
        request,
        "app/payments.html",
        {
            "title": "Мои оплаты preview",
            "user": preview["preview_user"],
            "snapshot": snapshot,
            "payment_status_label": payment_status_label,
            "billing_period_label": billing_period_label,
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
            "miniapp_active": "payments",
        },
    )


@router.get("/app/subscriptions", response_class=HTMLResponse)
async def preview_app_subscriptions(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    snapshot = preview["preview_snapshot"]
    return templates.TemplateResponse(
        request,
        "app/subscriptions.html",
        {
            "title": "Подписки preview",
            "user": preview["preview_user"],
            "snapshot": snapshot,
            "subscription_status_label": subscription_status_label,
            "billing_period_label": billing_period_label,
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
            "miniapp_active": "subscriptions",
        },
    )


@router.get("/app/help", response_class=HTMLResponse)
async def preview_app_help(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    snapshot = preview["preview_snapshot"]
    return templates.TemplateResponse(
        request,
        "app/help.html",
        {
            "title": "Помощь preview",
            "user": preview["preview_user"],
            "snapshot": snapshot,
            "telegram_bot_username": "preview_bot",
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
            "miniapp_active": "help",
        },
    )


@router.get("/app/payments/{payment_id}", response_class=HTMLResponse)
async def preview_app_payment_detail(payment_id: str, request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    payment = preview["preview_snapshot"].payments[0]
    if payment_id != payment.id:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "app/payment_detail.html",
        {
            "title": "Оплата preview",
            "user": preview["preview_user"],
            "payment": payment,
            "payment_history": payment_history(payment),
            "payment_result_message": payment_result_message(payment),
            "payment_status_label": payment_status_label,
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": preview["preview_snapshot"],
            "miniapp_active": "payments",
        },
    )


@router.post("/app/payments/{payment_id}/refresh")
async def preview_app_payment_refresh(payment_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/payments/{payment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/app/payments/{payment_id}/cancel")
async def preview_app_payment_cancel(payment_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/payments/{payment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/app/payments/{payment_id}/retry")
async def preview_app_payment_retry(payment_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/payments/{payment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/app/subscriptions/{subscription_id}", response_class=HTMLResponse)
async def preview_app_subscription_detail(subscription_id: str, request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    preview = build_preview_miniapp_context()
    snapshot = preview["preview_snapshot"]
    subscription = snapshot.subscriptions[0]
    if subscription_id != subscription.id:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "app/subscription_detail.html",
        {
            "title": "Подписка preview",
            "user": preview["preview_user"],
            "snapshot": snapshot,
            "subscription": subscription,
            "renewal_history": subscription_renewal_history(snapshot, subscription),
            "subscription_status_label": subscription_status_label,
            "billing_period_label": billing_period_label,
            "miniapp_mode": True,
            "preview_mode": True,
            "miniapp_user": preview["preview_user"],
            "miniapp_snapshot": snapshot,
            "miniapp_active": "subscriptions",
        },
    )


@router.post("/app/subscriptions/{subscription_id}/autorenew")
async def preview_app_subscription_autorenew(subscription_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/subscriptions/{subscription_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/app/subscriptions/{subscription_id}/renew")
async def preview_app_subscription_renew(subscription_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/subscriptions/{subscription_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/app/subscriptions/{subscription_id}/cancel")
async def preview_app_subscription_cancel(subscription_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url=f"/preview/app/subscriptions/{subscription_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/staff", include_in_schema=False)
async def preview_staff_root() -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    return RedirectResponse(url="/preview/admin/dashboard", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/admin/dashboard", response_class=HTMLResponse)
async def preview_admin_dashboard(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    context = build_preview_admin_context()
    return templates.TemplateResponse(
        request,
        "preview/admin_dashboard.html",
        context | {"title": "Admin preview", "preview_mode": True},
    )


@router.get("/author/dashboard", response_class=HTMLResponse)
async def preview_author_dashboard(request: Request) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    context = build_preview_author_context()
    return templates.TemplateResponse(
        request,
        "preview/author_dashboard.html",
        context | {"title": "Author preview", "preview_mode": True},
    )


@router.get("/author/recommendations/{recommendation_id}/preview", response_class=HTMLResponse)
async def preview_author_recommendation(request: Request, recommendation_id: str) -> Response:
    if not get_settings().app.preview_enabled:
        return _preview_disabled()
    context = build_preview_recommendation_context()
    recommendation = context["recommendation"]
    if recommendation_id != recommendation.id:
        return _preview_disabled()
    return templates.TemplateResponse(
        request,
        "app/recommendation_detail.html",
        {
            "title": recommendation.title,
            "user": context["user"],
            "recommendation": recommendation,
            "preview_mode": True,
            "attachment_download_enabled": False,
        },
    )
