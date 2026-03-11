from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from pitchcopytrade.auth.passwords import verify_password
from pitchcopytrade.db.models.accounts import User


async def get_user_by_identity(session: AsyncSession, identity: str) -> User | None:
    query = (
        select(User)
        .options(selectinload(User.roles), selectinload(User.author_profile))
        .where(or_(User.username == identity, User.email == identity))
    )
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def authenticate_user(session: AsyncSession, identity: str, password: str) -> User | None:
    user = await get_user_by_identity(session, identity)
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
