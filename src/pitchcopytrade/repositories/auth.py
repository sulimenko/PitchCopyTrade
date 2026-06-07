from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.repositories.contracts import AuthRepository
from pitchcopytrade.repositories.file_graph import FileDatasetGraph
from pitchcopytrade.repositories.file_store import FileDataStore


class SqlAlchemyAuthRepository(AuthRepository):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_identity(self, identity: str) -> User | None:
        query = (
            select(User)
            .options(selectinload(User.roles), selectinload(User.author_profile))
            .where(or_(User.username == identity, User.email == identity))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        query = (
            select(User)
            .options(selectinload(User.roles), selectinload(User.author_profile))
            .where(User.telegram_user_id == telegram_user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> User | None:
        query = (
            select(User)
            .options(selectinload(User.roles), selectinload(User.author_profile))
            .where(User.id == user_id)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def delete(self, entity: object) -> None:
        await self.session.delete(entity)

    async def commit(self) -> None:
        await self.session.commit()


class FileAuthRepository(AuthRepository):
    def __init__(self, store: FileDataStore | None = None) -> None:
        self.store = store or FileDataStore()
        self.graph = FileDatasetGraph.load(self.store)

    async def get_user_by_identity(self, identity: str) -> User | None:
        return next(
            (
                item
                for item in self.graph.users.values()
                if item.username == identity or item.email == identity
            ),
            None,
        )

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None:
        return next(
            (item for item in self.graph.users.values() if item.telegram_user_id == telegram_user_id),
            None,
        )

    async def get_user_by_id(self, user_id: str) -> User | None:
        return self.graph.users.get(user_id)

    async def delete(self, entity: object) -> None:
        self.graph.delete(entity)

    async def commit(self) -> None:
        self.graph.save(self.store)
