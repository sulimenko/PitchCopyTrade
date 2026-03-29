from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from pitchcopytrade.api.main import create_app
from pitchcopytrade.db.models.catalog import Instrument
from pitchcopytrade.db.models.enums import InstrumentType


class _FakeFileAuthorRepository:
    async def list_active_instruments(self):
        return [
            Instrument(
                id="instrument-1",
                ticker="NVTK",
                name="Novatek",
                board="TQBR",
                lot_size=10,
                currency="RUB",
                instrument_type=InstrumentType.EQUITY,
                is_active=True,
            )
        ]


def test_api_instruments_returns_quote_fields(monkeypatch) -> None:
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.instruments.get_settings",
        lambda: SimpleNamespace(app=SimpleNamespace(data_mode="file")),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.instruments.FileAuthorRepository",
        lambda: _FakeFileAuthorRepository(),
    )
    monkeypatch.setattr(
        "pitchcopytrade.api.routes.instruments.build_instrument_payloads",
        lambda instruments, allow_live_fetch=True: _async_return(
            [
                {
                    "id": item.id,
                    "ticker": item.ticker,
                    "name": item.name,
                    "board": item.board,
                    "currency": item.currency,
                    "is_active": item.is_active,
                    "last_price_text": "123.45",
                    "quote_last_price_text": "123.45",
                    "quote_change_text": "+1.20%",
                }
                for item in instruments
            ]
        ),
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/instruments?q=nvtk")

        assert response.status_code == 200
        payload = response.json()
        assert payload[0]["ticker"] == "NVTK"
        assert payload[0]["quote_last_price_text"] == "123.45"
        assert payload[0]["quote_change_text"] == "+1.20%"


async def _async_return(value):
    return value
