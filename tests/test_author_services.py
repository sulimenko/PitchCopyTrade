from __future__ import annotations

from io import BytesIO

import pytest
from starlette.datastructures import FormData, Headers, UploadFile

from pitchcopytrade.services.author import (
    add_author_watchlist_instrument,
    build_leg_rows_from_form,
    build_recommendation_form_data,
    normalize_attachment_uploads,
    remove_recommendation_attachments,
    search_author_watchlist_candidates,
)
from pitchcopytrade.db.models.content import Recommendation, RecommendationAttachment
from pitchcopytrade.db.models.catalog import Instrument
from pitchcopytrade.db.models.enums import InstrumentType
from pitchcopytrade.storage.local import LocalFilesystemStorage


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


def test_build_leg_rows_from_form_preserves_dynamic_indexes() -> None:
    form = FormData(
        {
            "leg_7_instrument_id": "instrument-7",
            "leg_7_side": "buy",
            "leg_7_entry_from": "101.5",
            "leg_12_instrument_id": "instrument-12",
            "leg_12_side": "sell",
            "leg_12_stop_loss": "99.2",
        }
    )

    rows = build_leg_rows_from_form(form)

    assert [row["row_id"] for row in rows] == ["7", "12"]
    assert rows[0]["instrument_id"] == "instrument-7"
    assert rows[1]["side"] == "sell"


def test_build_recommendation_form_data_requires_at_least_one_leg() -> None:
    with pytest.raises(ValueError, match="Добавьте минимум одну бумагу"):
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
            leg_rows=[],
            attachments=[],
        )


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


@pytest.mark.asyncio
async def test_remove_recommendation_attachments_deletes_local_blob(tmp_path) -> None:
    class DummyRepository:
        def __init__(self) -> None:
            self.deleted = []

        async def delete(self, entity) -> None:
            self.deleted.append(entity)

    repository = DummyRepository()
    recommendation = Recommendation(id="rec-1", strategy_id="strategy-1", author_id="author-1")
    attachment = RecommendationAttachment(
        id="att-1",
        recommendation_id="rec-1",
        object_key="recommendations/rec-1/file.pdf",
        original_filename="idea.pdf",
        content_type="application/pdf",
        size_bytes=8,
    )
    recommendation.attachments = [attachment]
    storage = LocalFilesystemStorage(root_dir=tmp_path / "storage" / "blob")
    storage.upload_bytes(attachment.object_key, b"pdf-data", "application/pdf")

    await remove_recommendation_attachments(repository, recommendation, ["att-1"], storage=storage)

    assert recommendation.attachments == []
    assert repository.deleted == [attachment]
    assert not (tmp_path / "storage" / "blob" / "recommendations" / "rec-1" / "file.pdf").exists()


@pytest.mark.asyncio
async def test_search_author_watchlist_candidates_excludes_existing_watchlist() -> None:
    author = type("Author", (), {"id": "author-1"})()
    existing = Instrument(
        id="instrument-1",
        ticker="SBER",
        name="Sberbank",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )
    candidate = Instrument(
        id="instrument-2",
        ticker="GAZP",
        name="Gazprom",
        board="TQBR",
        lot_size=10,
        currency="RUB",
        instrument_type=InstrumentType.EQUITY,
        is_active=True,
    )

    class DummyRepository:
        async def list_author_watchlist(self, author_id: str):
            assert author_id == "author-1"
            return [existing]

        async def list_active_instruments(self):
            return [existing, candidate]

    items = await search_author_watchlist_candidates(DummyRepository(), author, "gaz")

    assert [item.id for item in items] == ["instrument-2"]


@pytest.mark.asyncio
async def test_add_author_watchlist_instrument_raises_for_unknown_instrument() -> None:
    author = type("Author", (), {"id": "author-1"})()

    class DummyRepository:
        async def add_author_watchlist_instrument(self, author_id: str, instrument_id: str):
            assert author_id == "author-1"
            assert instrument_id == "unknown"
            return None

    with pytest.raises(ValueError, match="Инструмент не найден"):
        await add_author_watchlist_instrument(DummyRepository(), author, "unknown")
