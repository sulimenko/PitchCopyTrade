from __future__ import annotations

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.content import Message
from pitchcopytrade.repositories.contracts import AccessRepository


async def user_has_active_access(repository: AccessRepository, user_id: str) -> bool:
    return await repository.user_has_active_access(user_id)


async def list_user_visible_recommendations(
    repository: AccessRepository,
    *,
    user_id: str,
    limit: int = 20,
) -> list[Message]:
    return await repository.list_user_visible_messages(user_id=user_id, limit=limit)


async def get_user_visible_recommendation(
    repository: AccessRepository,
    *,
    user_id: str,
    recommendation_id: str,
) -> Message | None:
    return await repository.get_user_visible_message(user_id=user_id, message_id=recommendation_id)


async def get_user_by_telegram_id(repository: AccessRepository, telegram_user_id: int) -> User | None:
    return await repository.get_user_by_telegram_id(telegram_user_id)
