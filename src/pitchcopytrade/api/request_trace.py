from __future__ import annotations

from secrets import token_hex

from fastapi import Request, Response

from pitchcopytrade.core.config import get_settings


JOURNEY_COOKIE_NAME = "pct_journey_id"
ENTRY_QUERY_PARAM = "entry"
ENTRY_ID_FIELD = "entry_id"
ENTRY_SURFACE_FIELD = "entry_surface"

_STAGE_ALIASES = {
    "login_page": "login",
    "tg_webapp_auth_entry": "auth_entry",
    "tg_webapp_auth_failed": "auth_fail",
    "tg_webapp_auth_success": "auth_ok",
    "tg_webapp_bootstrap_trace": "bootstrap",
    "app_home_entry": "home",
    "miniapp_root": "miniapp_root",
    "verify_page": "verify",
    "catalog_render": "catalog",
    "strategy_render": "strategy",
    "checkout_render": "checkout_render",
    "checkout_submit": "checkout_submit",
    "checkout_submit_blocked": "checkout_blocked",
    "app_catalog_render": "app_catalog",
    "app_strategy_render": "app_strategy",
    "app_checkout_render": "checkout_render",
    "app_checkout_blocked": "checkout_blocked",
    "app_checkout_submit": "checkout_submit",
    "app_checkout_invalid": "checkout_invalid",
    "app_help_legacy_entry": "help_legacy",
    "subscriber_redirect_blocked": "sub_redirect_blocked",
    "subscriber_snapshot_blocked": "sub_snapshot_blocked",
    "subscriber_identity_blocked": "sub_identity_blocked",
    "staff_widget_callback_entry": "staff_callback_entry",
    "staff_invite_bind_success": "staff_bind_ok",
    "staff_invite_bind_failed": "staff_bind_fail",
    "staff_session_cookie_issued": "staff_cookie",
    "admin_dashboard_render": "admin_dashboard",
    "admin_dashboard_render_failed": "admin_dashboard_fail",
    "app_subscriptions_render": "subs_render",
    "app_subscriptions_render_failed": "subs_render_fail",
    "app_subscription_detail_render": "sub_detail",
    "app_subscription_detail_render_failed": "sub_detail_fail",
}


def get_or_create_journey_id(request: Request) -> str:
    return request.cookies.get(JOURNEY_COOKIE_NAME) or token_hex(8)


def attach_journey_cookie(response: Response, journey_id: str) -> Response:
    settings = get_settings()
    response.set_cookie(
        key=JOURNEY_COOKIE_NAME,
        value=journey_id,
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=settings.app.base_url.startswith("https://"),
        path="/",
    )
    return response


def classify_surface(request: Request) -> str:
    path = request.url.path
    if path == "/app":
        return "bootstrap"
    if path.startswith("/app/") or path.startswith("/preview/app/"):
        return "miniapp"
    if path.startswith("/verify/"):
        return "verify"
    if path.startswith("/miniapp") or path.startswith("/tg-webapp/") or path.startswith("/auth"):
        return "bootstrap"
    if path.startswith("/catalog") or path.startswith("/checkout") or path.startswith("/legal/"):
        return "public"
    return "unknown"


def get_entry_marker(request: Request) -> str | None:
    return request.query_params.get(ENTRY_QUERY_PARAM) or None


def compact_stage_name(stage: str) -> str:
    return _STAGE_ALIASES.get(stage, stage)


def checkout_validation_reason(message: str | None) -> str:
    normalized = (message or "").strip().lower()
    if not normalized:
        return "checkout_validation_error"
    if "checkout недоступен" in normalized or "не опубликован" in normalized or "published" in normalized:
        return "checkout_documents_unpublished"
    if ("обязатель" in normalized and "документ" in normalized) or "required documents" in normalized:
        return "missing_accepted_document_ids"
    if "telegram id" in normalized and "не найден" in normalized:
        return "missing_telegram_user_id"
    if "telegram context" in normalized:
        return "missing_telegram_context"
    return "checkout_validation_error"


def log_request_trace(
    logger,
    request: Request,
    *,
    stage: str,
    journey_id: str,
    surface: str | None = None,
    auth_user_id: str | None = None,
    telegram_user_id: int | None = None,
    telegram_cookie_present: bool | None = None,
    auth_cookie_present: bool | None = None,
    rendered_href: str | None = None,
    checkout_surface: str | None = None,
    telegram_intended: bool | None = None,
    block_reason: str | None = None,
    block_detail: str | None = None,
    entry_marker: str | None = None,
    entry_id: str | None = None,
    entry_surface: str | None = None,
    first_html_surface: str | None = None,
    requested_next: str | None = None,
    webapp_context_present: bool | None = None,
    legacy_entry: bool | None = None,
    init_data_length: int | None = None,
    init_data_has_hash: bool | None = None,
    init_data_has_auth_date: bool | None = None,
    init_data_has_user: bool | None = None,
    init_data_has_signature: bool | None = None,
    auth_date_age_seconds: int | None = None,
    redirect_target: str | None = None,
) -> None:
    settings = get_settings()
    telegram_cookie_name = f"{settings.auth.session_cookie_name}_tg"
    if telegram_cookie_present is None:
        telegram_cookie_present = bool(request.cookies.get(telegram_cookie_name))
    if auth_cookie_present is None:
        auth_cookie_present = bool(request.cookies.get(settings.auth.session_cookie_name))
    compact_stage = compact_stage_name(stage)
    logger.info(
        "%s trace journey_id=%s path=%s surface=%s entry_marker=%s entry_surface=%s resolved_user_id=%s resolved_telegram_user_id=%s redirect_target=%s block_reason=%s block_detail=%s",
        compact_stage,
        journey_id,
        request.url.path,
        surface or "-",
        entry_marker or "-",
        entry_surface or "-",
        auth_user_id or "-",
        telegram_user_id if telegram_user_id is not None else "-",
        redirect_target or "-",
        block_reason or "-",
        block_detail or "-",
    )
