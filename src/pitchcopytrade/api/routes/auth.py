from __future__ import annotations

from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.responses import Response
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.auth.roles import get_user_role_slugs
from pitchcopytrade.auth.service import authenticate_user
from pitchcopytrade.auth.session import (
    build_session_cookie_value,
    build_telegram_fallback_cookie_value,
    get_telegram_fallback_cookie_name,
    get_user_from_session_token,
    get_user_from_telegram_fallback_cookie,
    get_user_from_telegram_login_token,
)
from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.models.enums import RoleSlug
from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.web.templates import templates


router = APIRouter(tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, session: AsyncSession = Depends(get_db_session)) -> Response:
    token = request.cookies.get(get_settings().auth.session_cookie_name)
    user = await get_user_from_session_token(session, token) if token else None
    if user is not None:
        return RedirectResponse(url=_resolve_role_redirect(user), status_code=status.HTTP_303_SEE_OTHER)
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    tg_user = await get_user_from_telegram_fallback_cookie(session, tg_token) if tg_token else None
    if tg_user is not None:
        return RedirectResponse(url="/app/feed", status_code=status.HTTP_303_SEE_OTHER)

    return templates.TemplateResponse(
        request,
        "auth/login.html",
        {
            "title": "Вход в PitchCopyTrade",
            "error": None,
            "identity": "",
        },
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    identity: str = Form(...),
    password: str = Form(...),
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    user = await authenticate_user(session, identity.strip(), password)
    if user is None:
        return templates.TemplateResponse(
            request,
            "auth/login.html",
            {
                "title": "Вход в PitchCopyTrade",
                "error": "Неверный логин или пароль",
                "identity": identity.strip(),
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    settings = get_settings()
    response = RedirectResponse(url=_resolve_role_redirect(user), status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=settings.auth.session_cookie_name,
        value=build_session_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@router.get("/logout", include_in_schema=False)
async def logout() -> Response:
    settings = get_settings()
    response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    response.delete_cookie(settings.auth.session_cookie_name, path="/")
    response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
    return response


@router.get("/tg-auth", include_in_schema=False)
async def telegram_auth_login(
    token: str,
    session: AsyncSession = Depends(get_db_session),
) -> Response:
    user = await get_user_from_telegram_login_token(session, token)
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    settings = get_settings()
    response = RedirectResponse(url="/app/feed", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(
        key=get_telegram_fallback_cookie_name(),
        value=build_telegram_fallback_cookie_value(user),
        httponly=True,
        max_age=settings.auth.session_ttl_seconds,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@router.get("/app", response_class=HTMLResponse)
async def app_home(request: Request, session: AsyncSession = Depends(get_db_session)) -> Response:
    settings = get_settings()
    tg_token = request.cookies.get(get_telegram_fallback_cookie_name())
    if tg_token:
        subscriber = await get_user_from_telegram_fallback_cookie(session, tg_token)
        if subscriber is not None:
            return RedirectResponse(url="/app/feed", status_code=status.HTTP_303_SEE_OTHER)

    try:
        user = await _require_authenticated_user(request, session)
    except HTTPException:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.auth.session_cookie_name, path="/")
        response.delete_cookie(get_telegram_fallback_cookie_name(), path="/")
        return response

    redirect_url = _resolve_role_redirect(user)
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/workspace", response_class=HTMLResponse)
async def workspace_home(request: Request, session: AsyncSession = Depends(get_db_session)) -> Response:
    settings = get_settings()
    try:
        user = await _require_authenticated_user(request, session)
    except HTTPException:
        response = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
        response.delete_cookie(settings.auth.session_cookie_name, path="/")
        return response

    role_labels = sorted(role.value for role in get_user_role_slugs(user))
    return templates.TemplateResponse(
        request,
        "auth/app_home.html",
        {
            "title": "PitchCopyTrade Workspace",
            "user": user,
            "role_labels": role_labels,
            "role_home": _resolve_role_home(role_labels),
        },
    )


def _resolve_role_home(role_labels: list[str]) -> str:
    if RoleSlug.ADMIN.value in role_labels:
        return "Admin workspace"
    if RoleSlug.MODERATOR.value in role_labels:
        return "Moderator queue"
    return "Author workspace"


def _resolve_role_redirect(user) -> str:
    role_labels = {role.value for role in get_user_role_slugs(user)}
    if RoleSlug.ADMIN.value in role_labels:
        return "/admin/dashboard"
    if role_labels.intersection({RoleSlug.AUTHOR.value, RoleSlug.MODERATOR.value}):
        return "/workspace"
    return "/login"


async def _require_authenticated_user(request: Request, session: AsyncSession):
    settings = get_settings()
    token = request.cookies.get(settings.auth.session_cookie_name)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    user = await get_user_from_session_token(session, token)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
    return user
