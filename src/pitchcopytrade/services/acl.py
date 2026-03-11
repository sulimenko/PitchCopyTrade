from __future__ import annotations

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.repositories.access import SqlAlchemyAccessRepository


async def user_has_active_access(repository: SqlAlchemyAccessRepository, user_id: str) -> bool:
    return await repository.user_has_active_access(user_id)


async def list_user_visible_recommendations(
    repository: SqlAlchemyAccessRepository,
    *,
    user_id: str,
    limit: int = 20,
) -> list[Recommendation]:
    return await repository.list_user_visible_recommendations(user_id=user_id, limit=limit)


async def get_user_visible_recommendation(
    repository: SqlAlchemyAccessRepository,
    *,
    user_id: str,
    recommendation_id: str,
) -> Recommendation | None:
    return await repository.get_user_visible_recommendation(user_id=user_id, recommendation_id=recommendation_id)


async def get_user_by_telegram_id(repository: SqlAlchemyAccessRepository, telegram_user_id: int) -> User | None:
    return await repository.get_user_by_telegram_id(telegram_user_id)
