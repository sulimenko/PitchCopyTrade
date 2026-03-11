from __future__ import annotations

from fastapi import Depends

from pitchcopytrade.core.config import get_settings
from pitchcopytrade.db.session import get_optional_db_session
from pitchcopytrade.repositories.access import FileAccessRepository, SqlAlchemyAccessRepository
from pitchcopytrade.repositories.author import FileAuthorRepository, SqlAlchemyAuthorRepository
from sqlalchemy.ext.asyncio import AsyncSession


async def get_author_repository(session: AsyncSession | None = Depends(get_optional_db_session)):
    if get_settings().app.data_mode == "file":
        return FileAuthorRepository()
    if session is None:
        raise RuntimeError("Database session is required in APP_DATA_MODE=db")
    return SqlAlchemyAuthorRepository(session)


async def get_access_repository(session: AsyncSession | None = Depends(get_optional_db_session)):
    if get_settings().app.data_mode == "file":
        return FileAccessRepository()
    if session is None:
        raise RuntimeError("Database session is required in APP_DATA_MODE=db")
    return SqlAlchemyAccessRepository(session)
