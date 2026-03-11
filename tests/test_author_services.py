from __future__ import annotations

from io import BytesIO

import pytest
from starlette.datastructures import Headers, UploadFile

from pitchcopytrade.services.author import (
    build_recommendation_form_data,
    normalize_attachment_uploads,
)


@pytest.mark.asyncio
async def test_normalize_attachment_uploads_accepts_pdf() -> None:
    upload = UploadFile(file=BytesIO(b"pdf-data"), filename="idea.pdf", headers=Headers({"content-type": "application/pdf"}))

    items = await normalize_attachment_uploads([upload])

    assert len(items) == 1
    assert items[0].filename == "idea.pdf"
    assert items[0].content_type == "application/pdf"


@pytest.mark.asyncio
async def test_normalize_attachment_uploads_rejects_unsupported_type() -> None:
    upload = UploadFile(
        file=BytesIO(b"exe"),
        filename="bad.exe",
        headers=Headers({"content-type": "application/x-msdownload"}),
    )

    with pytest.raises(ValueError, match="Разрешены только PDF"):
        await normalize_attachment_uploads([upload])


def test_build_recommendation_form_data_parses_structured_leg() -> None:
    payload = build_recommendation_form_data(
        strategy_id="strategy-1",
        kind_value="new_idea",
        status_value="draft",
        title="Покупка SBER",
        summary="summary",
        thesis="thesis",
        market_context="context",
        requires_moderation=None,
        scheduled_for="",
        allowed_strategy_ids={"strategy-1"},
        allowed_instrument_ids={"instrument-1"},
        leg_rows=[
            {
                "instrument_id": "instrument-1",
                "side": "buy",
                "entry_from": "101.5",
                "entry_to": "102.1",
                "stop_loss": "99.9",
                "take_profit_1": "106.2",
                "take_profit_2": "",
                "take_profit_3": "",
                "time_horizon": "1-3 дня",
                "note": "Основной вход",
            }
        ],
        attachments=[],
    )

    assert len(payload.legs) == 1
    assert payload.legs[0].instrument_id == "instrument-1"
    assert str(payload.legs[0].entry_from) == "101.5"


def test_build_recommendation_form_data_rejects_unknown_instrument() -> None:
    with pytest.raises(ValueError, match="Leg 1: выберите допустимый инструмент"):
        build_recommendation_form_data(
            strategy_id="strategy-1",
            kind_value="new_idea",
            status_value="draft",
            title="Покупка SBER",
            summary="summary",
            thesis="thesis",
            market_context="context",
            requires_moderation=None,
            scheduled_for="",
            allowed_strategy_ids={"strategy-1"},
            allowed_instrument_ids={"instrument-1"},
            leg_rows=[
                {
                    "instrument_id": "bad",
                    "side": "buy",
                    "entry_from": "101.5",
                    "entry_to": "",
                    "stop_loss": "99.9",
                    "take_profit_1": "106.2",
                    "take_profit_2": "",
                    "take_profit_3": "",
                    "time_horizon": "",
                    "note": "",
                }
            ],
            attachments=[],
        )
