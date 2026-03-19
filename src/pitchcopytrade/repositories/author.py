from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationStatus
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


class SqlAlchemyAuthorRepository(AuthorRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_author_strategies(self, author_id: str) -> int:
        return await self._count(select(func.count(Strategy.id)).where(Strategy.author_id == author_id))

    async def count_author_recommendations(
        self,
        author_id: str,
        *,
        statuses: Sequence[RecommendationStatus] | None = None,
    ) -> int:
        query: Select[tuple[int]] = select(func.count(Recommendation.id)).where(Recommendation.author_id == author_id)
        if statuses:
            query = query.where(Recommendation.status.in_(statuses))
        return await self._count(query)

    async def list_author_strategies(self, author_id: str) -> list[Strategy]:
        query = select(Strategy).where(Strategy.author_id == author_id).order_by(Strategy.title.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_author_strategy(self, author_id: str, strategy_id: str) -> Strategy | None:
        query = (
            select(Strategy)
            .options(selectinload(Strategy.author))
            .where(Strategy.id == strategy_id, Strategy.author_id == author_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_active_instruments(self) -> list[Instrument]:
        query = select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.ticker.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_instrument(self, instrument_id: str) -> Instrument | None:
        query = select(Instrument).where(Instrument.id == instrument_id, Instrument.is_active.is_(True))
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_author_watchlist(self, author_id: str) -> list[Instrument]:
        author = await self.get_author_by_user_id_or_author_id(author_id)
        if author is None:
            return []
        return sorted(list(author.watchlist_instruments), key=lambda item: item.ticker.lower())

    async def add_author_watchlist_instrument(self, author_id: str, instrument_id: str) -> Instrument | None:
        author = await self.get_author_by_user_id_or_author_id(author_id)
        instrument = await self.get_instrument(instrument_id)
        if author is None or instrument is None:
            return None
        if instrument not in author.watchlist_instruments:
            author.watchlist_instruments.append(instrument)
            await self.session.commit()
            await self.session.refresh(author)
        return instrument

    async def list_author_recommendations(self, author_id: str) -> list[Recommendation]:
        query = (
            select(Recommendation)
            .options(
                selectinload(Recommendation.strategy),
                selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
                selectinload(Recommendation.attachments),
            )
            .where(Recommendation.author_id == author_id)
            .order_by(Recommendation.updated_at.desc(), Recommendation.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_author_recommendation(self, author_id: str, recommendation_id: str) -> Recommendation | None:
        query = (
            select(Recommendation)
            .options(
                selectinload(Recommendation.strategy),
                selectinload(Recommendation.legs).selectinload(RecommendationLeg.instrument),
                selectinload(Recommendation.attachments),
            )
            .where(Recommendation.id == recommendation_id, Recommendation.author_id == author_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_author_by_user_id(self, user_id: str) -> AuthorProfile | None:
        query = (
            select(AuthorProfile)
            .options(selectinload(AuthorProfile.user), selectinload(AuthorProfile.watchlist_instruments))
            .where(AuthorProfile.user_id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_author_by_user_id_or_author_id(self, author_id: str) -> AuthorProfile | None:
        query = (
            select(AuthorProfile)
            .options(selectinload(AuthorProfile.user), selectinload(AuthorProfile.watchlist_instruments))
            .where(AuthorProfile.id == author_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    def add(self, entity: object) -> None:
        self.session.add(entity)

    async def delete(self, entity: object) -> None:
        await self.session.delete(entity)

    async def flush(self) -> None:
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)

    async def _count(self, query: Select[tuple[int]]) -> int:
        result = await self.session.execute(query)
        return int(result.scalar_one())


class FileAuthorRepository(AuthorRepository):
    def __init__(self, store: FileDataStore | None = None) -> None:
        self.store = store or FileDataStore()
        self.graph = FileDatasetGraph.load(self.store)

    async def count_author_strategies(self, author_id: str) -> int:
        return len([item for item in self.graph.strategies.values() if item.author_id == author_id])

    async def count_author_recommendations(
        self,
        author_id: str,
        *,
        statuses: Sequence[RecommendationStatus] | None = None,
    ) -> int:
        items = [item for item in self.graph.recommendations.values() if item.author_id == author_id]
        if statuses:
            allowed = set(statuses)
            items = [item for item in items if item.status in allowed]
        return len(items)

    async def list_author_strategies(self, author_id: str) -> list[Strategy]:
        return sorted(
            [item for item in self.graph.strategies.values() if item.author_id == author_id],
            key=lambda item: item.title.lower(),
        )

    async def get_author_strategy(self, author_id: str, strategy_id: str) -> Strategy | None:
        strategy = self.graph.strategies.get(strategy_id)
        if strategy is None or strategy.author_id != author_id:
            return None
        return strategy

    async def list_active_instruments(self) -> list[Instrument]:
        return sorted(
            [item for item in self.graph.instruments.values() if item.is_active],
            key=lambda item: item.ticker.lower(),
        )

    async def get_instrument(self, instrument_id: str) -> Instrument | None:
        instrument = self.graph.instruments.get(instrument_id)
        if instrument is None or not instrument.is_active:
            return None
        return instrument

    async def list_author_watchlist(self, author_id: str) -> list[Instrument]:
        author = self.graph.authors.get(author_id)
        if author is None:
            return []
        return sorted(list(author.watchlist_instruments), key=lambda item: item.ticker.lower())

    async def add_author_watchlist_instrument(self, author_id: str, instrument_id: str) -> Instrument | None:
        author = self.graph.authors.get(author_id)
        instrument = await self.get_instrument(instrument_id)
        if author is None or instrument is None:
            return None
        if instrument not in author.watchlist_instruments:
            author.watchlist_instruments.append(instrument)
            if author not in instrument.watchlist_authors:
                instrument.watchlist_authors.append(author)
            self.graph.save(self.store)
        return instrument

    async def list_author_recommendations(self, author_id: str) -> list[Recommendation]:
        return sorted(
            [item for item in self.graph.recommendations.values() if item.author_id == author_id],
            key=lambda item: (item.updated_at, item.created_at),
            reverse=True,
        )

    async def get_author_recommendation(self, author_id: str, recommendation_id: str) -> Recommendation | None:
        recommendation = self.graph.recommendations.get(recommendation_id)
        if recommendation is None or recommendation.author_id != author_id:
            return None
        return recommendation

    async def get_author_by_user_id(self, user_id: str) -> AuthorProfile | None:
        return next((item for item in self.graph.authors.values() if item.user_id == user_id), None)

    def add(self, entity: object) -> None:
        self.graph.add(entity)

    async def delete(self, entity: object) -> None:
        self.graph.delete(entity)

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.graph.save(self.store)

    async def refresh(self, entity: object) -> None:
        return None
