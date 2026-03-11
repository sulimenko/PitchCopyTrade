from __future__ import annotations

from pitchcopytrade.auth.passwords import verify_password
from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.repositories.contracts import AuthRepository


async def get_user_by_identity(repository: AuthRepository, identity: str) -> User | None:
    return await repository.get_user_by_identity(identity)


async def authenticate_user(repository: AuthRepository, identity: str, password: str) -> User | None:
    user = await get_user_by_identity(repository, identity)
    if user is None or user.password_hash is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
