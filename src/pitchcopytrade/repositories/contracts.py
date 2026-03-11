from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from pitchcopytrade.db.models.accounts import AuthorProfile, User
from pitchcopytrade.db.models.catalog import Instrument, Strategy
from pitchcopytrade.db.models.content import Recommendation
from pitchcopytrade.db.models.enums import RecommendationStatus


class AuthorRepository(Protocol):
    async def count_author_strategies(self, author_id: str) -> int: ...

    async def count_author_recommendations(
        self,
        author_id: str,
        *,
        statuses: Sequence[RecommendationStatus] | None = None,
    ) -> int: ...

    async def list_author_strategies(self, author_id: str) -> list[Strategy]: ...

    async def list_active_instruments(self) -> list[Instrument]: ...

    async def list_author_recommendations(self, author_id: str) -> list[Recommendation]: ...

    async def get_author_recommendation(self, author_id: str, recommendation_id: str) -> Recommendation | None: ...

    async def get_author_by_user_id(self, user_id: str) -> AuthorProfile | None: ...

    def add(self, entity: object) -> None: ...

    async def delete(self, entity: object) -> None: ...

    async def flush(self) -> None: ...

    async def commit(self) -> None: ...

    async def refresh(self, entity: object) -> None: ...


class AccessRepository(Protocol):
    async def user_has_active_access(self, user_id: str) -> bool: ...

    async def list_user_visible_recommendations(
        self,
        *,
        user_id: str,
        limit: int = 20,
    ) -> list[Recommendation]: ...

    async def get_user_visible_recommendation(
        self,
        *,
        user_id: str,
        recommendation_id: str,
    ) -> Recommendation | None: ...

    async def get_user_by_telegram_id(self, telegram_user_id: int) -> User | None: ...
