from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from pitchcopytrade.db.models.accounts import Role, User, user_roles
from pitchcopytrade.db.models.enums import RoleSlug, UserStatus

logger = logging.getLogger(__name__)


async def seed_admin(session: AsyncSession, *, telegram_id: int | None, email: str | None) -> bool:
    if not telegram_id and not email:
        logger.info("No ADMIN_TELEGRAM_ID or ADMIN_EMAIL configured, skipping admin seeder")
        return False

    # Check if admin already exists
    query = (
        select(User)
        .join(user_roles, User.id == user_roles.c.user_id)
        .join(Role, Role.id == user_roles.c.role_id)
        .where(Role.slug == RoleSlug.ADMIN)
    )
    result = await session.execute(query)
    existing = result.scalar_one_or_none()
    if existing is not None:
        logger.info("Admin user already exists (id=%s), skipping", existing.id)
        return False

    # Get or create admin role
    role_result = await session.execute(select(Role).where(Role.slug == RoleSlug.ADMIN))
    admin_role = role_result.scalar_one_or_none()
    if admin_role is None:
        admin_role = Role(slug=RoleSlug.ADMIN, title="Администратор")
        session.add(admin_role)
        await session.flush()

    # Create admin user
    user = User(
        email=email,
        telegram_user_id=telegram_id,
        full_name="Администратор",
        status=UserStatus.ACTIVE,
    )
    session.add(user)
    await session.flush()

    user.roles.append(admin_role)
    await session.commit()

    logger.info("Admin user created (id=%s, telegram_id=%s, email=%s)", user.id, telegram_id, email)
    return True
