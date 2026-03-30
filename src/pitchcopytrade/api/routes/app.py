from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response, StreamingResponse

from pitchcopytrade.api.deps.repositories import get_access_repository, get_auth_repository, get_public_repository
from pitchcopytrade.api.request_trace import (
    attach_journey_cookie,
    get_entry_marker,
    get_or_create_journey_id,
    log_request_trace,
)
from pitchcopytrade.auth.session import get_telegram_fallback_cookie_name, get_user_from_telegram_fallback_cookie
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.repositories.contracts import AccessRepository, AuthRepository, PublicRepository
from pitchcopytrade.services.acl import (
    get_user_visible_recommendation,
    list_user_visible_recommendations,
    user_has_active_access,
)
from pitchcopytrade.services.public import (
    TelegramSubscriberProfile,
    build_strategy_story,
    create_telegram_stub_checkout,
    get_public_product,
    get_public_strategy_by_slug,
    list_active_checkout_documents,
    list_public_strategies,
)
from pitchcopytrade.services.instruments import build_strategy_quote_strip
from pitchcopytrade.services.subscriber import SubscriberStatusSnapshot, get_subscriber_status_snapshot
from pitchcopytrade.services.subscriber import (
    billing_period_label,
    build_action_cards,
    build_subscriber_timeline,
    cancel_subscription,
    cancel_pending_payment,
    get_notification_preferences,
    list_reminder_center_entries,
    payment_status_label,
    payment_history,
    payment_result_message,
    refresh_pending_payment,
    renew_subscription_checkout,
    retry_payment_checkout,
    subscription_renewal_history,
    subscription_status_label,
    toggle_subscription_autorenew,
    update_notification_preferences,
)
from pitchcopytrade.storage.local import LocalFilesystemStorage
from pitchcopytrade.web.templates import templates


router = APIRouter(prefix="/app", tags=["app"])
logger = logging.getLogger(__name__)


def _with_entry_marker(url: str, entry_marker: str | None) -> str:
    if not entry_marker:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}entry={entry_marker}"


def _verify_redirect_url(requested_next: str) -> str:
    return f"/verify/telegram?next=/app/catalog&requested_next={quote(requested_next, safe='/')}"


@router.get("/catalog", response_class=HTMLResponse)
async def app_catalog(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user

    journey_id = get_or_create_journey_id(request)
    entry_marker = get_entry_marker(request) or "bot_start"
    strategies = await list_public_strategies(public_repository)
    for strategy in strategies:
        strategy.detail_href = _with_entry_marker(f"/app/strategies/{strategy.slug}", "miniapp_catalog")
        for product in strategy.subscription_products:
            product.checkout_href = _with_entry_marker(f"/app/checkout/{product.slug}", "miniapp_catalog")
        strategy.story = build_strategy_story(strategy)
        strategy.quotes = await build_strategy_quote_strip(strategy)
    log_request_trace(
        logger,
        request,
        stage="app_catalog_render",
        journey_id=journey_id,
        surface="miniapp",
        auth_user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        rendered_href=_with_entry_marker("/app/catalog", entry_marker),
        checkout_surface="miniapp",
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="miniapp",
        first_html_surface="app/catalog",
        requested_next="/app/catalog",
    )
    response = templates.TemplateResponse(
        request,
        "public/catalog.html",
        {
            "title": "Каталог Mini App",
            "strategies": strategies,
            "telegram_bot_username": get_settings().telegram.bot_username,
            "entry_marker": entry_marker,
            **_build_miniapp_context("catalog", user=user, snapshot=snapshot),
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/strategies/{slug}", response_class=HTMLResponse)
async def app_strategy_detail(
    slug: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user

    journey_id = get_or_create_journey_id(request)
    entry_marker = get_entry_marker(request) or "bot_start"
    strategy = await get_public_strategy_by_slug(public_repository, slug)
    if strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    strategy.detail_href = _with_entry_marker(f"/app/strategies/{strategy.slug}", "miniapp_strategy")
    strategy.story = build_strategy_story(strategy)
    strategy.quotes = await build_strategy_quote_strip(strategy)
    for product in strategy.subscription_products:
        product.checkout_href = _with_entry_marker(f"/app/checkout/{product.slug}", "miniapp_strategy")
    log_request_trace(
        logger,
        request,
        stage="app_strategy_render",
        journey_id=journey_id,
        surface="miniapp",
        auth_user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        rendered_href=_with_entry_marker(f"/app/strategies/{slug}", entry_marker),
        checkout_surface="miniapp",
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="miniapp",
        first_html_surface="app/catalog",
        requested_next="/app/catalog",
    )
    response = templates.TemplateResponse(
        request,
        "public/strategy_detail.html",
        {
            "title": strategy.title,
            "strategy": strategy,
            "billing_period_label": billing_period_label,
            "entry_marker": entry_marker,
            **_build_miniapp_context("catalog", user=user, snapshot=snapshot),
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/checkout/{product_ref}", response_class=HTMLResponse)
async def app_checkout_page(
    product_ref: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user

    journey_id = get_or_create_journey_id(request)
    entry_marker = get_entry_marker(request) or "bot_start"
    product = await get_public_product(public_repository, product_ref)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product_title = product.title
    entry_marker = get_entry_marker(request) or "bot_start"
    documents = await list_active_checkout_documents(public_repository)
    checkout_ready = len(documents) == 4
    log_request_trace(
        logger,
        request,
        stage="app_checkout_render",
        journey_id=journey_id,
        surface="miniapp",
        auth_user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        rendered_href=_with_entry_marker(f"/app/checkout/{product_ref}", entry_marker),
        checkout_surface="miniapp",
        telegram_intended=True,
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="miniapp",
        first_html_surface="app/catalog",
        requested_next="/app/catalog",
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
            "entry_marker": entry_marker,
            "error": None,
            "form_values": {
                "full_name": user.full_name or "",
                "email": user.email or "",
                "timezone_name": user.timezone or "Europe/Moscow",
                "lead_source_name": "telegram_miniapp",
                "promo_code_value": "",
                "accepted_document_ids": [],
                "entry_id": journey_id,
                "entry_surface": "miniapp",
            },
            **_build_miniapp_context("catalog", user=user, snapshot=snapshot),
        },
    )
    return attach_journey_cookie(response, journey_id)


@router.post("/checkout/{product_ref}", response_class=HTMLResponse)
async def app_checkout_submit(
    product_ref: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
    full_name: str = Form(""),
    email: str = Form(""),
    timezone_name: str = Form("Europe/Moscow"),
    accepted_document_ids: list[str] = Form(...),
    promo_code_value: str = Form(""),
    entry_id: str = Form(""),
    entry_surface: str = Form(""),
) -> Response:
    user = await _get_subscriber_or_redirect(request, auth_repository)
    if isinstance(user, Response):
        return user
    journey_id = get_or_create_journey_id(request)
    resolved_entry_id = entry_id.strip() or journey_id
    resolved_entry_surface = entry_surface.strip() or "miniapp"
    if not user.telegram_user_id:
        logger.error("Mini App checkout: user %s has no telegram_user_id", user.id)
        block = RedirectResponse(url=_verify_redirect_url(f"/app/checkout/{product_ref}"), status_code=status.HTTP_303_SEE_OTHER)
        log_request_trace(
            logger,
            request,
            stage="app_checkout_blocked",
            journey_id=journey_id,
            surface="miniapp",
            auth_user_id=user.id,
            telegram_user_id=user.telegram_user_id,
            rendered_href=_with_entry_marker(f"/app/checkout/{product_ref}", get_entry_marker(request) or resolved_entry_surface),
            checkout_surface="miniapp",
            telegram_intended=True,
            block_reason="missing_telegram_user_id",
            entry_marker=get_entry_marker(request) or resolved_entry_surface,
            entry_id=resolved_entry_id,
            entry_surface=resolved_entry_surface,
            first_html_surface="telegram_verify",
            requested_next=f"/app/checkout/{product_ref}",
        )
        return attach_journey_cookie(block, journey_id)
    snapshot = await get_subscriber_status_snapshot(access_repository, telegram_user_id=user.telegram_user_id)
    if snapshot is None:
        response = RedirectResponse(url=_verify_redirect_url(f"/app/checkout/{product_ref}"), status_code=status.HTTP_303_SEE_OTHER)
        log_request_trace(
            logger,
            request,
            stage="app_checkout_blocked",
            journey_id=journey_id,
            surface="miniapp",
            auth_user_id=user.id,
            telegram_user_id=user.telegram_user_id,
            rendered_href=_with_entry_marker(f"/app/checkout/{product_ref}", get_entry_marker(request) or resolved_entry_surface),
            checkout_surface="miniapp",
            telegram_intended=True,
            block_reason="missing_subscriber_snapshot",
            entry_marker=get_entry_marker(request) or resolved_entry_surface,
            entry_id=resolved_entry_id,
            entry_surface=resolved_entry_surface,
            first_html_surface="telegram_verify",
            requested_next=f"/app/checkout/{product_ref}",
        )
        return attach_journey_cookie(response, journey_id)

    product = await get_public_product(public_repository, product_ref)
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    product_title = product.title
    documents = await list_active_checkout_documents(public_repository)
    checkout_ready = len(documents) == 4
    checkout_email = email.strip().lower() or user.email
    logger.info(
        "Mini App checkout route path=%s auth_user_id=%s auth_telegram_user_id=%s checkout_email=%s product_ref=%s",
        request.url.path,
        user.id,
        user.telegram_user_id,
        checkout_email,
        product_ref,
    )
    log_request_trace(
        logger,
        request,
        stage="app_checkout_submit",
        journey_id=journey_id,
        surface="miniapp",
        auth_user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        rendered_href=_with_entry_marker(f"/app/checkout/{product_ref}", get_entry_marker(request) or resolved_entry_surface),
        checkout_surface="miniapp",
        telegram_intended=True,
        entry_marker=get_entry_marker(request) or resolved_entry_surface,
        entry_id=resolved_entry_id,
        entry_surface=resolved_entry_surface,
        first_html_surface="app/catalog",
        requested_next=f"/app/checkout/{product_ref}",
    )
    try:
        result = await create_telegram_stub_checkout(
            public_repository,
            product=product,
            profile=TelegramSubscriberProfile(
                telegram_user_id=user.telegram_user_id,
                username=user.username,
                first_name=None,
                last_name=None,
                full_name=full_name.strip() or user.full_name,
                email=checkout_email,
                timezone_name=timezone_name.strip() or user.timezone or "Europe/Moscow",
                lead_source_name="telegram_miniapp",
            ),
            accepted_document_ids=accepted_document_ids,
            promo_code_value=promo_code_value.strip().upper() or None,
        )
    except ValueError as exc:
        response = templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product_title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "error": str(exc),
                "form_values": {
                    "full_name": full_name,
                    "email": checkout_email or "",
                    "timezone_name": timezone_name,
                    "lead_source_name": "telegram_miniapp",
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids,
                    "entry_id": resolved_entry_id,
                "entry_surface": resolved_entry_surface,
            },
                **_build_miniapp_context("catalog", user=user, snapshot=snapshot),
            },
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        )
        return attach_journey_cookie(response, journey_id)
    except Exception:
        logger.exception("Mini App checkout creation failed for product %s", product_ref)
        response = templates.TemplateResponse(
            request,
            "public/checkout.html",
            {
                "title": f"Подписка {product_title}",
                "product": product,
                "documents": documents,
                "checkout_ready": checkout_ready,
                "payment_provider": get_settings().payments.provider,
                "error": "Не удалось создать заявку на оплату. Попробуйте еще раз.",
                "form_values": {
                    "full_name": full_name,
                    "email": checkout_email or "",
                    "timezone_name": timezone_name,
                    "lead_source_name": "telegram_miniapp",
                    "promo_code_value": promo_code_value,
                    "accepted_document_ids": accepted_document_ids,
                    "entry_id": resolved_entry_id,
                "entry_surface": resolved_entry_surface,
            },
                **_build_miniapp_context("catalog", user=user, snapshot=snapshot),
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
            "entry_id": resolved_entry_id,
            "entry_surface": resolved_entry_surface,
            **_build_miniapp_context("payments", user=user, snapshot=snapshot),
        },
        status_code=status.HTTP_201_CREATED,
    )
    return attach_journey_cookie(response, journey_id)


@router.get("/feed", response_class=HTMLResponse)
async def app_feed(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    recommendations = await list_user_visible_recommendations(repository, user_id=user.id)
    has_access = await user_has_active_access(repository, user_id=user.id)
    return templates.TemplateResponse(
        request,
        "app/feed.html",
        {
            "title": "Лента рекомендаций",
            "user": user,
            "recommendations": recommendations,
            "has_access": has_access,
            **_build_miniapp_context("feed", user=user, snapshot=snapshot),
        },
    )


@router.get("/status", response_class=HTMLResponse)
async def app_status(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user

    return templates.TemplateResponse(
        request,
        "app/status.html",
        {
            "title": "Статус подписки",
            "user": user,
            "snapshot": snapshot,
            "action_cards": build_action_cards(snapshot),
            "payment_status_label": payment_status_label,
            "subscription_status_label": subscription_status_label,
            **_build_miniapp_context("status", user=user, snapshot=snapshot),
        },
    )


@router.get("/subscriptions", response_class=HTMLResponse)
async def app_subscriptions(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    return templates.TemplateResponse(
        request,
        "app/subscriptions.html",
        {
            "title": "Мои подписки",
            "user": user,
            "snapshot": snapshot,
            "subscription_status_label": subscription_status_label,
            "billing_period_label": billing_period_label,
            **_build_miniapp_context("subscriptions", user=user, snapshot=snapshot),
        },
    )


@router.get("/payments", response_class=HTMLResponse)
async def app_payments(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    return templates.TemplateResponse(
        request,
        "app/payments.html",
        {
            "title": "Мои оплаты",
            "user": user,
            "snapshot": snapshot,
            "payment_status_label": payment_status_label,
            **_build_miniapp_context("payments", user=user, snapshot=snapshot),
        },
    )


@router.get("/subscriptions/{subscription_id}", response_class=HTMLResponse)
async def app_subscription_detail(
    subscription_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    subscription = next((item for item in snapshot.subscriptions if item.id == subscription_id), None)
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return templates.TemplateResponse(
        request,
        "app/subscription_detail.html",
        {
            "title": "Подписка",
            "user": user,
            "snapshot": snapshot,
            "subscription": subscription,
            "renewal_history": subscription_renewal_history(snapshot, subscription),
            "subscription_status_label": subscription_status_label,
            "billing_period_label": billing_period_label,
            **_build_miniapp_context("subscriptions", user=user, snapshot=snapshot),
        },
    )


@router.post("/subscriptions/{subscription_id}/autorenew")
async def app_subscription_autorenew(
    subscription_id: str,
    request: Request,
    enabled: str = Form(...),
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    subscription = await toggle_subscription_autorenew(
        public_repository,
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
        enabled=enabled == "1",
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return RedirectResponse(url=f"/app/subscriptions/{subscription_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/subscriptions/{subscription_id}/renew")
async def app_subscription_renew(
    subscription_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
    promo_code_value: str = Form(""),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    result = await renew_subscription_checkout(
        public_repository,
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
        promo_code_value=promo_code_value.strip().upper() or None,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return RedirectResponse(url=f"/app/payments/{result.payment.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/subscriptions/{subscription_id}/cancel")
async def app_subscription_cancel(
    subscription_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    subscription = await cancel_subscription(
        public_repository,
        telegram_user_id=telegram_user_id,
        subscription_id=subscription_id,
    )
    if subscription is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
    return RedirectResponse(url=f"/app/subscriptions/{subscription_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/help", response_class=HTMLResponse)
async def app_help(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    return templates.TemplateResponse(
        request,
        "app/help.html",
        {
            "title": "Помощь",
            "user": user,
            "snapshot": snapshot,
            "telegram_bot_username": get_settings().telegram.bot_username,
            **_build_miniapp_context("help", user=user, snapshot=snapshot),
        },
    )


@router.get("/reminders", response_class=HTMLResponse)
async def app_reminders(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    preferences = await get_notification_preferences(repository, user_id=user.id)
    reminders = await list_reminder_center_entries(repository, user_id=user.id)
    return templates.TemplateResponse(
        request,
        "app/reminders.html",
        {
            "title": "Напоминания",
            "user": user,
            "snapshot": snapshot,
            "preferences": preferences,
            "reminders": reminders,
            **_build_miniapp_context("reminders", user=user, snapshot=snapshot),
        },
    )


@router.post("/reminders/preferences")
async def app_reminder_preferences_submit(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
    payment_reminders: str | None = Form(default=None),
    subscription_reminders: str | None = Form(default=None),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    await update_notification_preferences(
        repository,
        user_id=user.id,
        payment_reminders=payment_reminders is not None,
        subscription_reminders=subscription_reminders is not None,
    )
    return RedirectResponse(url="/app/reminders", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/timeline", response_class=HTMLResponse)
async def app_timeline(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    timeline = build_subscriber_timeline(snapshot)
    return templates.TemplateResponse(
        request,
        "app/timeline.html",
        {
            "title": "История событий",
            "user": user,
            "snapshot": snapshot,
            "timeline": timeline,
            **_build_miniapp_context("timeline", user=user, snapshot=snapshot),
        },
    )


@router.get("/payments/{payment_id}", response_class=HTMLResponse)
async def app_payment_detail(
    payment_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    payment = next((item for item in snapshot.payments if item.id == payment_id), None)
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return templates.TemplateResponse(
        request,
        "app/payment_detail.html",
        {
            "title": "Оплата",
            "user": user,
            "snapshot": snapshot,
            "payment": payment,
            "payment_history": payment_history(payment),
            "payment_result_message": payment_result_message(payment),
            "payment_status_label": payment_status_label,
            **_build_miniapp_context("payments", user=user, snapshot=snapshot),
        },
    )


@router.post("/payments/{payment_id}/cancel")
async def app_payment_cancel(
    payment_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    payment = await cancel_pending_payment(
        public_repository,
        telegram_user_id=telegram_user_id,
        payment_id=payment_id,
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return RedirectResponse(url=f"/app/payments/{payment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/payments/{payment_id}/refresh")
async def app_payment_refresh(
    payment_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    payment = await refresh_pending_payment(
        public_repository,
        telegram_user_id=telegram_user_id,
        payment_id=payment_id,
    )
    if payment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return RedirectResponse(url=f"/app/payments/{payment_id}", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/payments/{payment_id}/retry")
async def app_payment_retry(
    payment_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    access_repository: AccessRepository = Depends(get_access_repository),
    public_repository: PublicRepository = Depends(get_public_repository),
    promo_code_value: str = Form(""),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, access_repository)
    if isinstance(user, Response):
        return user
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return telegram_user_id
    result = await retry_payment_checkout(
        public_repository,
        telegram_user_id=telegram_user_id,
        payment_id=payment_id,
        promo_code_value=promo_code_value.strip().upper() or None,
    )
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    return RedirectResponse(url=f"/app/payments/{result.payment.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/messages/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_detail_page(
    recommendation_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    recommendation = await get_user_visible_recommendation(
        repository,
        user_id=user.id,
        recommendation_id=recommendation_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return templates.TemplateResponse(
        request,
        "app/message_detail.html",
        {
            "title": recommendation.title or "Сообщение",
            "user": user,
            "message": recommendation,
            "thread_messages": [recommendation],
            "preview_mode": False,
            "attachment_download_enabled": True,
            **_build_miniapp_context("feed", user=user, snapshot=snapshot),
        },
    )


@router.get("/messages/{recommendation_id}/attachments/{attachment_id}")
async def recommendation_attachment_download(
    recommendation_id: str,
    attachment_id: str,
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
    repository: AccessRepository = Depends(get_access_repository),
) -> Response:
    user, _snapshot = await _get_subscriber_snapshot_or_redirect(request, auth_repository, repository)
    if isinstance(user, Response):
        return user
    recommendation = await get_user_visible_recommendation(
        repository,
        user_id=user.id,
        recommendation_id=recommendation_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    attachment = next((item for item in recommendation.documents if item.get("id") == attachment_id), None)
    if attachment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")

    try:
        payload = LocalFilesystemStorage().download_bytes(str(attachment.get("key") or attachment.get("object_key")))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment file not found") from exc
    filename = attachment.get("name") or attachment.get("title") or attachment.get("original_filename") or "attachment"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([payload]),
        media_type=attachment.get("type") or attachment.get("content_type") or "application/octet-stream",
        headers=headers,
    )


async def _get_subscriber_or_redirect(request: Request, repository: AuthRepository) -> User | Response:
    journey_id = get_or_create_journey_id(request)
    requested_next = request.url.path
    entry_marker = get_entry_marker(request)
    token = request.cookies.get(get_telegram_fallback_cookie_name())
    if not token:
        log_request_trace(
            logger,
            request,
            stage="subscriber_redirect_blocked",
            journey_id=journey_id,
            surface="miniapp",
            entry_marker=entry_marker,
            entry_id=journey_id,
            entry_surface="bootstrap",
            first_html_surface="telegram_verify",
            requested_next=requested_next,
            block_reason="no_telegram_cookie",
        )
        response = RedirectResponse(url=_verify_redirect_url(requested_next), status_code=status.HTTP_303_SEE_OTHER)
        return attach_journey_cookie(response, journey_id)

    user = await get_user_from_telegram_fallback_cookie(repository, token)
    if user is not None:
        return user

    log_request_trace(
        logger,
        request,
        stage="subscriber_redirect_blocked",
        journey_id=journey_id,
        surface="miniapp",
        entry_marker=entry_marker,
        entry_id=journey_id,
        entry_surface="bootstrap",
        first_html_surface="telegram_verify",
        requested_next=requested_next,
        block_reason="invalid_telegram_cookie",
    )
    response = RedirectResponse(url=_verify_redirect_url(requested_next), status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
    return attach_journey_cookie(response, journey_id)


async def _get_subscriber_snapshot_or_redirect(
    request: Request,
    auth_repository: AuthRepository,
    access_repository: AccessRepository,
) -> tuple[User | Response, SubscriberStatusSnapshot | None]:
    user = await _get_subscriber_or_redirect(request, auth_repository)
    if isinstance(user, Response):
        return user, None
    telegram_user_id = _require_telegram_user_id_or_redirect(user, request)
    if isinstance(telegram_user_id, Response):
        return attach_journey_cookie(telegram_user_id, get_or_create_journey_id(request)), None
    snapshot = await get_subscriber_status_snapshot(access_repository, telegram_user_id=telegram_user_id)
    if snapshot is None:
        journey_id = get_or_create_journey_id(request)
        log_request_trace(
            logger,
            request,
            stage="subscriber_snapshot_blocked",
            journey_id=journey_id,
            surface="miniapp",
            auth_user_id=user.id,
            telegram_user_id=telegram_user_id,
            entry_marker=get_entry_marker(request),
            entry_id=journey_id,
            entry_surface="bootstrap",
            first_html_surface="telegram_verify",
            requested_next=request.url.path,
            block_reason="missing_subscriber_snapshot",
        )
        response = RedirectResponse(url=_verify_redirect_url(request.url.path), status_code=status.HTTP_303_SEE_OTHER)
        return attach_journey_cookie(response, journey_id), None
    return user, snapshot


def _build_miniapp_context(
    active_tab: str,
    *,
    user: User,
    snapshot: SubscriberStatusSnapshot,
) -> dict[str, object]:
    return {
        "miniapp_mode": True,
        "miniapp_active": active_tab,
        "miniapp_user": user,
        "miniapp_snapshot": snapshot,
    }


def _require_telegram_user_id_or_redirect(user: User, request: Request) -> int | Response:
    telegram_user_id = user.telegram_user_id
    if telegram_user_id is not None:
        return telegram_user_id
    logger.warning("Mini App user %s has no telegram_user_id; redirecting to verification", user.id)
    journey_id = get_or_create_journey_id(request)
    log_request_trace(
        logger,
        request,
        stage="subscriber_identity_blocked",
        journey_id=journey_id,
        surface="miniapp",
        auth_user_id=user.id,
        telegram_user_id=user.telegram_user_id,
        entry_marker=get_entry_marker(request),
        entry_id=journey_id,
        entry_surface="bootstrap",
        first_html_surface="telegram_verify",
        requested_next=request.url.path,
        block_reason="missing_telegram_user_id",
    )
    return RedirectResponse(
        url=_verify_redirect_url(request.url.path),
        status_code=status.HTTP_303_SEE_OTHER,
    )


# Phase 9 routes: /my, /strategy/{slug}, /auth redirect

@router.get("/strategy/{slug}", response_class=HTMLResponse)
async def app_strategy_detail_alias(
    slug: str,
    request: Request,
) -> Response:
    return RedirectResponse(url=f"/app/strategies/{slug}", status_code=status.HTTP_301_MOVED_PERMANENTLY)


@router.get("/my", response_class=HTMLResponse)
async def app_my_subscriptions(request: Request) -> Response:
    return RedirectResponse(url="/app/subscriptions", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/auth", response_class=HTMLResponse, include_in_schema=False)
async def app_auth_redirect(request: Request) -> Response:
    return RedirectResponse(url="/tg-webapp/auth", status_code=status.HTTP_303_SEE_OTHER)
