from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import asyncio
import logging
import re

import httpx

from pitchcopytrade.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True, frozen=True)
class InstrumentQuote:
    ticker: str
    source: str
    status: str
    last_price: float | None
    change_pct: float | None
    change_abs: float | None
    currency: str | None
    updated_at: str | None
    is_stale: bool = False
    provider_symbol: str | None = None
    payload: dict[str, object] | None = None

    @property
    def last_price_text(self) -> str:
        if self.last_price is None:
            return "—"
        return _format_price(self.last_price)

    @property
    def change_text(self) -> str:
        if self.change_pct is None and self.change_abs is None:
            return "—"
        parts: list[str] = []
        if self.change_abs is not None:
            parts.append(_format_change(self.change_abs))
        if self.change_pct is not None:
            pct = f"{self.change_pct:+.2f}%"
            parts.append(pct.replace("+", "+").replace("-", "−"))
        return " / ".join(parts) if parts else "—"

    def as_dict(self) -> dict[str, object]:
        return {
            "ticker": self.ticker,
            "source": self.source,
            "status": self.status,
            "last_price": self.last_price,
            "change_pct": self.change_pct,
            "change_abs": self.change_abs,
            "currency": self.currency,
            "updated_at": self.updated_at,
            "is_stale": self.is_stale,
            "provider_symbol": self.provider_symbol,
            "last_price_text": self.last_price_text,
            "change_text": self.change_text,
        }


@dataclass(slots=True)
class _QuoteCacheEntry:
    quote: InstrumentQuote
    expires_at: datetime


_QUOTE_CACHE: dict[str, _QuoteCacheEntry] = {}
_QUOTE_CACHE_LOCK = asyncio.Lock()


def clear_instrument_quote_cache() -> None:
    _QUOTE_CACHE.clear()


async def get_instrument_quote(ticker: str, *, allow_live_fetch: bool = True) -> InstrumentQuote:
    settings = get_settings().instrument_quotes
    normalized_ticker = _normalize_ticker(ticker)
    logger.info(
        "Fetching quote for %s: provider_enabled=%s, url=%s",
        normalized_ticker or ticker,
        settings.provider_enabled,
        settings.provider_base_url,
    )
    if not normalized_ticker:
        return _empty_quote("", source="meta.pbull.kz", status="empty")
    if not settings.provider_enabled:
        logger.warning("Instrument quote provider disabled for %s", normalized_ticker)
        return _empty_quote(normalized_ticker, source="meta.pbull.kz", status="disabled")

    cached_quote = await _get_cached_quote(normalized_ticker)
    if cached_quote is not None:
        return cached_quote

    if not allow_live_fetch:
        stale_quote = await _get_stale_cached_quote(normalized_ticker)
        if stale_quote is not None:
            return stale_quote
        return _empty_quote(normalized_ticker, source=_provider_source(settings), status="empty")

    try:
        quote = await _fetch_quote(normalized_ticker, settings=settings)
    except Exception as exc:  # pragma: no cover - defensive logging, covered by tests via fallback
        logger.warning("Instrument quote lookup failed for %s: %s", normalized_ticker, exc)
        stale_quote = await _get_stale_cached_quote(normalized_ticker)
        if stale_quote is not None:
            return stale_quote
        return _empty_quote(normalized_ticker, source=_provider_source(settings), status="empty")

    await _store_quote(normalized_ticker, quote, ttl_seconds=settings.cache_ttl_seconds)
    return quote


async def build_instrument_payload(instrument, *, allow_live_fetch: bool = True) -> dict[str, object]:
    quote = await get_instrument_quote(instrument.ticker, allow_live_fetch=allow_live_fetch)
    if quote.status in {"empty", "disabled"}:
        log = logger.warning if allow_live_fetch else logger.info
        log("No quote for %s: status=%s", instrument.ticker, quote.status)
    logger.info(
        "Instrument payload for %s: quote_status=%s, last_price=%s",
        instrument.ticker,
        quote.status,
        quote.last_price,
    )
    payload = {
        "id": instrument.id,
        "ticker": instrument.ticker,
        "name": instrument.name,
        "board": instrument.board,
        "currency": instrument.currency,
        "is_active": instrument.is_active,
        "last_price": quote.last_price,
        "change_pct": quote.change_pct,
        "change_abs": quote.change_abs,
        "quote_status": quote.status,
        "quote_source": quote.source,
        "quote_is_stale": quote.is_stale,
        "quote_last_price_text": quote.last_price_text,
        "quote_change_text": quote.change_text,
        "quote_updated_at": quote.updated_at,
        "quote": quote.as_dict(),
    }
    return payload


async def build_instrument_payloads(instruments, *, allow_live_fetch: bool = True) -> list[dict[str, object]]:
    unique_instruments = []
    seen: set[str] = set()
    for instrument in instruments:
        key = str(getattr(instrument, "id", "") or getattr(instrument, "ticker", "")).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique_instruments.append(instrument)
    return await asyncio.gather(
        *(build_instrument_payload(instrument, allow_live_fetch=allow_live_fetch) for instrument in unique_instruments)
    )


async def build_quote_strip(tickers: list[str]) -> list[InstrumentQuote]:
    unique_tickers = []
    seen: set[str] = set()
    for ticker in tickers:
        normalized = _normalize_ticker(ticker)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_tickers.append(normalized)
    return await asyncio.gather(*(get_instrument_quote(ticker) for ticker in unique_tickers))


async def build_strategy_quote_strip(strategy) -> list[InstrumentQuote]:
    quote_tickers = []
    story = getattr(strategy, "story", None)
    if story is not None:
        quote_tickers.extend(extract_tickers_from_text("\n".join(getattr(story, "instrument_examples", []) or [])))
    quote_tickers.extend(extract_tickers_from_text(getattr(strategy, "short_description", "") or ""))
    quote_tickers.extend(extract_tickers_from_text(getattr(strategy, "full_description", "") or ""))
    return await build_quote_strip(quote_tickers)


def extract_tickers_from_text(text: str) -> list[str]:
    if not text.strip():
        return []
    candidates = re.findall(r"\b[A-Z][A-Z0-9]{1,7}\b", text)
    ignored = {"FAQ", "CTA", "RUB", "BUY", "SELL", "TP", "SL", "HTTP", "HTTPS"}
    return [candidate for candidate in candidates if candidate not in ignored]


async def _get_cached_quote(ticker: str) -> InstrumentQuote | None:
    async with _QUOTE_CACHE_LOCK:
        entry = _QUOTE_CACHE.get(ticker)
        if entry is None:
            return None
        if entry.expires_at <= datetime.now(timezone.utc):
            return None
        return entry.quote


async def _get_stale_cached_quote(ticker: str) -> InstrumentQuote | None:
    async with _QUOTE_CACHE_LOCK:
        entry = _QUOTE_CACHE.get(ticker)
        if entry is None:
            return None
        return InstrumentQuote(
            ticker=entry.quote.ticker,
            source=entry.quote.source,
            status="stale",
            last_price=entry.quote.last_price,
            change_pct=entry.quote.change_pct,
            change_abs=entry.quote.change_abs,
            currency=entry.quote.currency,
            updated_at=entry.quote.updated_at,
            is_stale=True,
            provider_symbol=entry.quote.provider_symbol,
            payload=entry.quote.payload,
        )


async def _store_quote(ticker: str, quote: InstrumentQuote, *, ttl_seconds: int) -> None:
    async with _QUOTE_CACHE_LOCK:
        _QUOTE_CACHE[ticker] = _QuoteCacheEntry(
            quote=quote,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds),
        )


async def _fetch_quote(ticker: str, *, settings) -> InstrumentQuote:
    url = settings.provider_base_url
    logger.info("Quote HTTP request: GET %s?symbol=%s", url, ticker)
    async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
        response = await client.get(url, params={"symbol": ticker})
    response_body = getattr(response, "content", b"") or b""
    logger.info("Quote HTTP response: status=%s, body_length=%s", response.status_code, len(response_body))
    if len(response_body) < 2000:
        logger.info(
            "Quote response body for %s: %s",
            ticker,
            response_body.decode("utf-8", errors="replace")[:500],
        )
    response.raise_for_status()
    payload = response.json()
    normalized = _normalize_provider_payload(ticker, payload, source=_provider_source(settings))
    if normalized is None:
        return _empty_quote(ticker, source=_provider_source(settings), status="empty")
    return normalized


def _normalize_provider_payload(ticker: str, payload: object, *, source: str) -> InstrumentQuote | None:
    unwrapped = _unwrap_payload(payload)
    if isinstance(unwrapped, dict) and ticker in unwrapped and isinstance(unwrapped[ticker], dict):
        data = unwrapped[ticker]
    else:
        data = unwrapped
    if not isinstance(data, dict):
        logger.warning("Provider payload for %s is not a dict: %s", ticker, type(data))
        return None

    symbol = _first_text(
        data,
        "symbol",
        "ticker",
        "secCode",
        "sec_code",
        "code",
        "short_name",
    )

    last_price = _nested_float(data, "trade.price")
    if last_price is None:
        last_price = _nested_float(data, "daily-bar.close")
    if last_price is None:
        last_price = _first_float(data, "lastPrice", "last_price", "price", "close", "ltp", "marketPrice")

    prev_close = _nested_float(data, "prev-daily-bar.close")
    if prev_close is None:
        prev_close = _first_float(data, "prev_close_price", "previousClose")
    if last_price is not None and prev_close is not None:
        change_abs = round(last_price - prev_close, 6)
    else:
        change_abs = _first_float(data, "change", "delta", "priceChange", "change_value", "absChange")
    if last_price is not None and prev_close is not None and prev_close != 0:
        change_pct = round((last_price - prev_close) / prev_close * 100, 2)
    else:
        change_pct = _first_float(data, "changePercent", "change_pct", "change_percentage", "percentChange", "chp")
    currency = _first_text(data, "currency_code", "currency", "curr", "priceCurrency", "currency_id")
    updated_at = (
        _nested_text(data, "trade.time")
        or _nested_text(data, "trade.data-update-time")
        or _first_text(data, "updatedAt", "updated_at", "time", "timestamp", "datetime", "lastUpdate")
    )
    status = _first_text(data, "status", "state", "tradeStatus") or ("ok" if last_price is not None else "empty")

    if last_price is None and change_abs is None and change_pct is None and symbol == "" and len(data) == 0:
        return None

    return InstrumentQuote(
        ticker=ticker,
        source=source,
        status=status,
        last_price=last_price,
        change_pct=change_pct,
        change_abs=change_abs,
        currency=currency,
        updated_at=updated_at,
        provider_symbol=symbol or ticker,
        payload=data,
    )


def _unwrap_payload(payload: object) -> object:
    if not isinstance(payload, dict):
        return payload
    for key in ("data", "result", "quote", "payload"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            return nested
        if isinstance(nested, list) and nested and isinstance(nested[0], dict):
            return nested[0]
    return payload


def _first_text(data: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _first_float(data: dict[str, object], *keys: str) -> float | None:
    for key in keys:
        value = data.get(key)
        number = _coerce_float(value)
        if number is not None:
            return number
    return None


def _nested_float(data: dict[str, object], path: str) -> float | None:
    current: object = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
        if current is None:
            return None
    return _coerce_float(current)


def _nested_text(data: dict[str, object], path: str) -> str:
    current: object = data
    for key in path.split("."):
        if not isinstance(current, dict):
            return ""
        current = current.get(key)
        if current is None:
            return ""
    return str(current).strip()


def _coerce_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.replace(" ", "").replace(",", ".").strip()
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _normalize_ticker(value: str) -> str:
    return value.strip().upper()


def _provider_source(settings) -> str:
    return settings.provider_base_url


def _empty_quote(ticker: str, *, source: str, status: str) -> InstrumentQuote:
    return InstrumentQuote(
        ticker=ticker,
        source=source,
        status=status,
        last_price=None,
        change_pct=None,
        change_abs=None,
        currency=None,
        updated_at=None,
        is_stale=False,
        provider_symbol=ticker or None,
        payload=None,
    )


def _format_price(value: float) -> str:
    if value.is_integer():
        return f"{int(value):,}".replace(",", " ")
    return f"{value:,.2f}".replace(",", " ")


def _format_change(value: float) -> str:
    prefix = "+" if value >= 0 else "−"
    magnitude = abs(value)
    if magnitude.is_integer():
        rendered = f"{int(magnitude):,}".replace(",", " ")
    else:
        rendered = f"{magnitude:,.2f}".replace(",", " ")
    return f"{prefix}{rendered}"
