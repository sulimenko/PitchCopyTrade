from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json

from pitchcopytrade.db.models.enums import RoleSlug


class AuthTokenError(ValueError):
    pass


@dataclass(frozen=True)
class SessionTokenPayload:
    subject: str
    issued_at: datetime
    expires_at: datetime
    roles: tuple[RoleSlug, ...]
    token_type: str = "session"


def create_session_token(
    *,
    user_id: str,
    role_slugs: set[RoleSlug],
    secret_key: str,
    ttl_seconds: int,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": user_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "roles": sorted(role.value for role in role_slugs),
        "typ": "session",
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(body, secret_key)
    return f"{body}.{signature}"


def decode_session_token(token: str, *, secret_key: str, now: datetime | None = None) -> SessionTokenPayload:
    try:
        body, signature = token.split(".", 1)
    except ValueError as exc:
        raise AuthTokenError("Invalid token format") from exc

    expected_signature = _sign(body, secret_key)
    if not hmac.compare_digest(signature, expected_signature):
        raise AuthTokenError("Invalid token signature")

    payload = json.loads(_b64decode(body).decode("utf-8"))
    current_time = int((now or datetime.now(timezone.utc)).timestamp())
    if payload["exp"] < current_time:
        raise AuthTokenError("Token expired")
    if payload.get("typ") not in {"session", "telegram_login", "staff_invite"}:
        raise AuthTokenError("Unsupported token type")

    return SessionTokenPayload(
        subject=payload["sub"],
        issued_at=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        roles=tuple(RoleSlug(role) for role in payload.get("roles", [])),
        token_type=payload.get("typ", "session"),
    )


def create_telegram_login_token(
    *,
    user_id: str,
    secret_key: str,
    ttl_seconds: int = 600,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": user_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "roles": [],
        "typ": "telegram_login",
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(body, secret_key)
    return f"{body}.{signature}"


def create_staff_invite_token(
    *,
    user_id: str,
    secret_key: str,
    ttl_seconds: int = 7 * 24 * 60 * 60,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    payload = {
        "sub": user_id,
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
        "roles": [],
        "typ": "staff_invite",
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _sign(body, secret_key)
    return f"{body}.{signature}"


def decode_telegram_login_token(token: str, *, secret_key: str, now: datetime | None = None) -> SessionTokenPayload:
    payload = decode_session_token(token, secret_key=secret_key, now=now)
    if payload.token_type != "telegram_login":
        raise AuthTokenError("Unsupported token type")
    return payload


def decode_staff_invite_token(token: str, *, secret_key: str, now: datetime | None = None) -> SessionTokenPayload:
    payload = decode_session_token(token, secret_key=secret_key, now=now)
    if payload.token_type != "staff_invite":
        raise AuthTokenError("Unsupported token type")
    return payload


def _sign(body: str, secret_key: str) -> str:
    return _b64encode(hmac.new(secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest())


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
