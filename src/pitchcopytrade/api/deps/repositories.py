from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.session import get_db_session
from pitchcopytrade.repositories.access import SqlAlchemyAccessRepository
from pitchcopytrade.repositories.author import SqlAlchemyAuthorRepository


async def get_author_repository(session: AsyncSession = Depends(get_db_session)) -> SqlAlchemyAuthorRepository:
    return SqlAlchemyAuthorRepository(session)


async def get_access_repository(session: AsyncSession = Depends(get_db_session)) -> SqlAlchemyAccessRepository:
    return SqlAlchemyAccessRepository(session)
