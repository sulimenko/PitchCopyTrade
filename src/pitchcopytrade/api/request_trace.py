from __future__ import annotations

from secrets import token_hex

from fastapi import Request, Response

from pitchcopytrade.core.config import get_settings


JOURNEY_COOKIE_NAME = "pct_journey_id"
ENTRY_QUERY_PARAM = "entry"
ENTRY_ID_FIELD = "entry_id"
ENTRY_SURFACE_FIELD = "entry_surface"


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
    entry_marker: str | None = None,
    entry_id: str | None = None,
    entry_surface: str | None = None,
    first_html_surface: str | None = None,
    requested_next: str | None = None,
) -> None:
    settings = get_settings()
    telegram_cookie_name = f"{settings.auth.session_cookie_name}_tg"
    if telegram_cookie_present is None:
        telegram_cookie_present = bool(request.cookies.get(telegram_cookie_name))
    if auth_cookie_present is None:
        auth_cookie_present = bool(request.cookies.get(settings.auth.session_cookie_name))
    logger.info(
        "%s trace journey_id=%s surface=%s classified_surface=%s path=%s query=%s entry_marker=%s entry_id=%s entry_surface=%s first_html_surface=%s requested_next=%s referer=%s origin=%s user_agent=%s sec_fetch_site=%s sec_fetch_mode=%s telegram_cookie_present=%s auth_cookie_present=%s resolved_user_id=%s resolved_telegram_user_id=%s rendered_href=%s checkout_surface=%s telegram_intended=%s block_reason=%s",
        stage,
        journey_id,
        surface or "-",
        classify_surface(request),
        request.url.path,
        request.url.query or "-",
        entry_marker or "-",
        entry_id or "-",
        entry_surface or "-",
        first_html_surface or "-",
        requested_next or "-",
        request.headers.get("referer") or "-",
        request.headers.get("origin") or "-",
        request.headers.get("user-agent") or "-",
        request.headers.get("sec-fetch-site") or "-",
        request.headers.get("sec-fetch-mode") or "-",
        telegram_cookie_present,
        auth_cookie_present,
        auth_user_id or "-",
        telegram_user_id if telegram_user_id is not None else "-",
        rendered_href or "-",
        checkout_surface or "-",
        telegram_intended if telegram_intended is not None else "-",
        block_reason or "-",
    )
