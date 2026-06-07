from __future__ import annotations

import re

import pytest
from sqlalchemy.exc import IntegrityError

from pitchcopytrade.db.models.catalog import Strategy
from pitchcopytrade.db.models.enums import RiskLevel, StrategyStatus
from pitchcopytrade.services.admin import StrategyFormData, create_strategy, update_strategy


class FakeStrategySession:
    def __init__(self, *, existing: list[Strategy] | None = None, commit_error: Exception | None = None) -> None:
        self.existing = existing or []
        self.commit_error = commit_error
        self.added: list[object] = []
        self.commits = 0
        self.rollback_called = False

    async def execute(self, query):
        compiled = str(query.compile(compile_kwargs={"literal_binds": True}))
        slug_match = re.search(r"strategies\.slug = '([^']+)'", compiled)
        exclude_match = re.search(r"strategies\.id != '([^']+)'", compiled)
        target_slug = slug_match.group(1) if slug_match else None
        excluded_id = exclude_match.group(1) if exclude_match else None

        class Result:
            def __init__(self, value: Strategy | None) -> None:
                self._value = value

            def scalar_one_or_none(self) -> Strategy | None:
                return self._value

        if target_slug is not None:
            for item in self.existing:
                if item.slug == target_slug and (excluded_id is None or item.id != excluded_id):
                    return Result(item)
        return Result(None)

    def add(self, entity: object) -> None:
        self.added.append(entity)

    async def commit(self) -> None:
        self.commits += 1
        if self.commit_error is not None:
            raise self.commit_error

    async def refresh(self, entity: object) -> None:
        return None

    async def rollback(self) -> None:
        self.rollback_called = True


def _make_strategy(*, strategy_id: str, slug: str, status: StrategyStatus = StrategyStatus.DRAFT) -> Strategy:
    return Strategy(
        id=strategy_id,
        author_id="author-1",
        slug=slug,
        title="Value RU",
        short_description="Стратегия",
        full_description="Описание",
        risk_level=RiskLevel.MEDIUM,
        status=status,
        min_capital_rub=150000,
        is_public=True,
    )


@pytest.mark.asyncio
async def test_create_strategy_rejects_duplicate_slug_before_insert() -> None:
    session = FakeStrategySession(existing=[_make_strategy(strategy_id="strategy-1", slug="growth-ru")])
    data = StrategyFormData(
        author_id="author-1",
        slug="growth-ru",
        title="Growth RU",
        short_description="Тестовая стратегия",
        full_description=None,
        risk_level=RiskLevel.HIGH,
        status=StrategyStatus.DRAFT,
        min_capital_rub=250000,
        is_public=True,
    )

    with pytest.raises(ValueError, match="уже используется"):
        await create_strategy(session, data)

    assert session.added == []
    assert session.commits == 0
    assert session.rollback_called is False


@pytest.mark.asyncio
async def test_create_strategy_rolls_back_on_integrity_error() -> None:
    session = FakeStrategySession(commit_error=IntegrityError("stmt", {}, Exception("unique violation")))
    data = StrategyFormData(
        author_id="author-1",
        slug="growth-ru",
        title="Growth RU",
        short_description="Тестовая стратегия",
        full_description=None,
        risk_level=RiskLevel.HIGH,
        status=StrategyStatus.DRAFT,
        min_capital_rub=250000,
        is_public=True,
    )

    with pytest.raises(ValueError, match="уже используется"):
        await create_strategy(session, data)

    assert session.added, "strategy should be added before the commit fails"
    assert session.commits == 1
    assert session.rollback_called is True


@pytest.mark.asyncio
async def test_update_strategy_rejects_duplicate_slug_for_other_strategy() -> None:
    session = FakeStrategySession(existing=[_make_strategy(strategy_id="strategy-2", slug="growth-ru")])
    strategy = _make_strategy(strategy_id="strategy-1", slug="value-ru")
    data = StrategyFormData(
        author_id="author-1",
        slug="growth-ru",
        title="Growth RU",
        short_description="Тестовая стратегия",
        full_description=None,
        risk_level=RiskLevel.HIGH,
        status=StrategyStatus.DRAFT,
        min_capital_rub=250000,
        is_public=True,
    )

    with pytest.raises(ValueError, match="уже используется"):
        await update_strategy(session, strategy, data)

    assert session.commits == 0
    assert session.rollback_called is False

