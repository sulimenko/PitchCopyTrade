from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation, RecommendationLeg
from pitchcopytrade.db.models.enums import RecommendationStatus


class SqlAlchemyAuthorRepository:
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

    async def list_active_instruments(self) -> list[Instrument]:
        query = select(Instrument).where(Instrument.is_active.is_(True)).order_by(Instrument.ticker.asc())
        result = await self.session.execute(query)
        return list(result.scalars().all())

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
            .options(selectinload(AuthorProfile.user))
            .where(AuthorProfile.user_id == user_id)
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
