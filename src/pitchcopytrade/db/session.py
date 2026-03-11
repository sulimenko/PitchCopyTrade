from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from pitchcopytrade.core.config import get_settings

settings = get_settings()
engine = create_async_engine(settings.database.url, pool_pre_ping=True) if settings.app.data_mode == "db" else None
AsyncSessionLocal = (
    async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    if engine is not None
    else None
)


async def get_db_session():
    if AsyncSessionLocal is None:
        raise RuntimeError("Database session is unavailable in APP_DATA_MODE=file")
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        try:
            await session.close()
        except ValueError as exc:
            if "greenlet" not in str(exc):
                raise


async def get_optional_db_session():
    if AsyncSessionLocal is None:
        yield None
        return
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        try:
            await session.close()
        except ValueError as exc:
            if "greenlet" not in str(exc):
                raise
