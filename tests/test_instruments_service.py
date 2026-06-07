from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import httpx
import pytest

from pitchcopytrade.services import instruments as instrument_service


class _FakeResponse:
    def __init__(self, payload: object, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                "bad response",
                request=httpx.Request("GET", "https://example.test"),
                response=httpx.Response(self.status_code, request=httpx.Request("GET", "https://example.test")),
            )

    def json(self) -> object:
        return self._payload


class _FakeAsyncClient:
    def __init__(self, payload: object | Exception, *, status_code: int = 200, **_kwargs) -> None:
        self.payload = payload
        self.status_code = status_code

    async def __aenter__(self) -> "_FakeAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def get(self, url: str, params: dict[str, object] | None = None) -> _FakeResponse:
        if isinstance(self.payload, Exception):
            raise self.payload
        return _FakeResponse(self.payload, status_code=self.status_code)


def _enable_quotes(monkeypatch: pytest.MonkeyPatch, *, origin: str = "https://meta.pbull.kz") -> None:
    provider_base_url = f"{origin.rstrip('/')}/api/marketData/forceDataSymbol"
    monkeypatch.setattr(
        instrument_service,
        "get_settings",
        lambda: SimpleNamespace(
            instrument_quotes=SimpleNamespace(
                provider_enabled=True,
                provider_base_url=provider_base_url,
                timeout_seconds=1.0,
                cache_ttl_seconds=60,
            )
        ),
    )


@pytest.mark.asyncio
async def test_get_instrument_quote_normalizes_provider_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    _enable_quotes(monkeypatch)
    monkeypatch.setattr(
        instrument_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(
            {
                "NVTK": {
                    "symbol": "NVTK",
                    "lastPrice": "123.45",
                    "changePercent": "1.25",
                    "change": "1.53",
                    "currency": "RUB",
                    "updatedAt": "2026-03-26T10:00:00+00:00",
                }
            }
        ),
    )

    quote = await instrument_service.get_instrument_quote("NVTK")

    assert quote.ticker == "NVTK"
    assert quote.source == "https://meta.pbull.kz/api/marketData/forceDataSymbol"
    assert quote.status == "ok"
    assert quote.last_price == 123.45
    assert quote.change_pct == 1.25
    assert quote.change_abs == 1.53
    assert quote.last_price_text == "123.45"
    assert quote.change_text == "+1.53 / +1.25%"


@pytest.mark.asyncio
async def test_get_instrument_quote_prefers_nested_trade_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    _enable_quotes(monkeypatch)
    monkeypatch.setattr(
        instrument_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(
            {
                "GAZP": {
                    "symbol": "GAZP",
                    "short_name": "GAZP",
                    "description": "Gazprom",
                    "trade": {
                        "price": "137.32",
                        "time": "1774778083",
                    },
                    "prev-daily-bar": {
                        "close": "137.09",
                    },
                    "daily-bar": {
                        "close": "137.32",
                    },
                    "currency_code": "RUB",
                    "lp": 1.68214032,
                    "chp": 0.18,
                    "ch": 0.003,
                    "prev_close_price": 1.6790783200000001,
                }
            }
        ),
    )

    quote = await instrument_service.get_instrument_quote("GAZP")

    assert quote.ticker == "GAZP"
    assert quote.provider_symbol == "GAZP"
    assert quote.last_price == 137.32
    assert quote.change_abs == pytest.approx(0.23)
    assert quote.change_pct == pytest.approx(0.17)
    assert quote.currency == "RUB"
    assert quote.updated_at == "1774778083"


@pytest.mark.asyncio
async def test_get_instrument_quote_returns_stale_cache_on_provider_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    _enable_quotes(monkeypatch)
    cached_quote = instrument_service.InstrumentQuote(
        ticker="NVTK",
        source="https://meta.pbull.kz/api/marketData/forceDataSymbol",
        status="ok",
        last_price=111.0,
        change_pct=0.5,
        change_abs=0.5,
        currency="RUB",
        updated_at="2026-03-26T09:00:00+00:00",
    )
    instrument_service._QUOTE_CACHE["NVTK"] = instrument_service._QuoteCacheEntry(
        quote=cached_quote,
        expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    monkeypatch.setattr(
        instrument_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(httpx.ConnectError("boom", request=httpx.Request("GET", "https://example.test"))),
    )

    quote = await instrument_service.get_instrument_quote("NVTK")

    assert quote.status == "stale"
    assert quote.is_stale is True
    assert quote.last_price == 111.0


@pytest.mark.asyncio
async def test_get_instrument_quote_returns_empty_on_failure_without_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    _enable_quotes(monkeypatch)
    monkeypatch.setattr(
        instrument_service.httpx,
        "AsyncClient",
        lambda **kwargs: _FakeAsyncClient(httpx.ConnectError("boom", request=httpx.Request("GET", "https://example.test"))),
    )

    quote = await instrument_service.get_instrument_quote("NVTK")

    assert quote.status == "empty"
    assert quote.is_stale is False
    assert quote.last_price is None


@pytest.mark.asyncio
async def test_get_instrument_quote_skips_live_fetch_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    _enable_quotes(monkeypatch)

    def fail_on_client(**_kwargs):
        raise AssertionError("live fetch should not be used when allow_live_fetch is False")

    monkeypatch.setattr(instrument_service.httpx, "AsyncClient", fail_on_client)

    quote = await instrument_service.get_instrument_quote("NVTK", allow_live_fetch=False)

    assert quote.status == "empty"
    assert quote.is_stale is False
    assert quote.last_price is None


@pytest.mark.asyncio
async def test_build_instrument_payloads_deduplicates_instruments_by_identity(monkeypatch: pytest.MonkeyPatch) -> None:
    instrument_service.clear_instrument_quote_cache()
    calls: list[str] = []

    async def fake_build_instrument_payload(instrument, *, allow_live_fetch: bool = True):
        calls.append(f"{instrument.id}:{allow_live_fetch}")
        return {"id": instrument.id, "ticker": instrument.ticker}

    monkeypatch.setattr(instrument_service, "build_instrument_payload", fake_build_instrument_payload)

    instruments = [
        SimpleNamespace(id="instrument-1", ticker="NVTK"),
        SimpleNamespace(id="instrument-1", ticker="NVTK"),
    ]

    payloads = await instrument_service.build_instrument_payloads(instruments, allow_live_fetch=False)

    assert payloads == [{"id": "instrument-1", "ticker": "NVTK"}]
    assert calls == ["instrument-1:False"]
