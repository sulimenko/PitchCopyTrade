from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.repositories.contracts import AuthorRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


class SqlAlchemyAuthorRepository(AuthorRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def count_author_strategies(self, author_id: str) -> int:
        return await self._count(select(func.count(Strategy.id)).where(Strategy.author_id == author_id))

    async def count_author_messages(self, author_id: str) -> int:
        query: Select[tuple[int]] = select(func.count(Message.id)).where(Message.author_id == author_id)
        return await self._count(query)

    async def count_author_recommendations(self, author_id: str) -> int:
        return await self.count_author_messages(author_id)

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

    async def get_instrument_by_ticker(self, ticker: str) -> Instrument | None:
        normalized = ticker.strip().upper()
        if not normalized:
            return None
        query = select(Instrument).where(func.upper(Instrument.ticker) == normalized)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

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

    async def remove_author_watchlist_instrument(self, author_id: str, instrument_id: str) -> bool:
        author = await self.get_author_by_user_id_or_author_id(author_id)
        if author is None:
            return False
        instrument = next((item for item in author.watchlist_instruments if item.id == instrument_id), None)
        if instrument is None:
            return False
        author.watchlist_instruments.remove(instrument)
        await self.session.commit()
        await self.session.refresh(author)
        return True

    async def list_author_messages(self, author_id: str) -> list[Message]:
        query = (
            select(Message)
            .options(
                selectinload(Message.strategy),
                selectinload(Message.author),
                selectinload(Message.user),
                selectinload(Message.moderator),
                selectinload(Message.bundle),
            )
            .where(Message.author_id == author_id)
            .order_by(Message.updated.desc(), Message.created.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_author_message(self, author_id: str, message_id: str) -> Message | None:
        query = (
            select(Message)
            .options(
                selectinload(Message.strategy),
                selectinload(Message.author),
                selectinload(Message.user),
                selectinload(Message.moderator),
                selectinload(Message.bundle),
            )
            .where(Message.id == message_id, Message.author_id == author_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_author_recommendations(self, author_id: str) -> list[Message]:
        return await self.list_author_messages(author_id)

    async def get_author_recommendation(self, author_id: str, recommendation_id: str) -> Message | None:
        return await self.get_author_message(author_id, recommendation_id)

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

    async def count_author_messages(self, author_id: str) -> int:
        return len([item for item in self.graph.messages.values() if item.author_id == author_id])

    async def count_author_recommendations(self, author_id: str) -> int:
        return await self.count_author_messages(author_id)

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

    async def get_instrument_by_ticker(self, ticker: str) -> Instrument | None:
        normalized = ticker.strip().upper()
        if not normalized:
            return None
        return next((item for item in self.graph.instruments.values() if item.ticker.strip().upper() == normalized), None)

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

    async def remove_author_watchlist_instrument(self, author_id: str, instrument_id: str) -> bool:
        author = self.graph.authors.get(author_id)
        if author is None:
            return False
        instrument = next((item for item in author.watchlist_instruments if item.id == instrument_id), None)
        if instrument is None:
            return False
        author.watchlist_instruments.remove(instrument)
        if author in instrument.watchlist_authors:
            instrument.watchlist_authors.remove(author)
        self.graph.save(self.store)
        return True

    async def list_author_messages(self, author_id: str) -> list[Message]:
        return sorted(
            [item for item in self.graph.messages.values() if item.author_id == author_id],
            key=lambda item: (item.updated, item.created),
            reverse=True,
        )

    async def get_author_message(self, author_id: str, message_id: str) -> Message | None:
        message = self.graph.messages.get(message_id)
        if message is None or message.author_id != author_id:
            return None
        return message

    async def list_author_recommendations(self, author_id: str) -> list[Message]:
        return await self.list_author_messages(author_id)

    async def get_author_recommendation(self, author_id: str, recommendation_id: str) -> Message | None:
        return await self.get_author_message(author_id, recommendation_id)

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
