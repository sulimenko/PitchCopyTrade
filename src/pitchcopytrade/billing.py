from __future__ import annotations

from datetime import timedelta

ALLOWED_DURATION_DAYS: tuple[int, ...] = (30, 60, 90, 180, 365)

_DURATION_DAY_LABELS = {
    30: "30 дней",
    60: "60 дней",
    90: "90 дней",
    180: "180 дней",
    365: "1 год",
}


def normalize_duration_days(value: object | None) -> int | None:
    if value is None:
        return None
    raw = getattr(value, "duration_days", value)
    if hasattr(raw, "value"):
        raw = getattr(raw, "value")
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
    try:
        days = int(raw)
    except (TypeError, ValueError):
        return None
    if days not in ALLOWED_DURATION_DAYS:
        return None
    return days


def duration_days_label(value: object | None) -> str:
    if value is None:
        return "Период не указан"
    days = normalize_duration_days(value)
    if days is None:
        return str(getattr(value, "value", value))
    return _DURATION_DAY_LABELS.get(days, f"{days} дней")


def subscription_delta(duration_days: int) -> timedelta:
    return timedelta(days=duration_days)
