from __future__ import annotations

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import RoleSlug


def get_user_role_slugs(user: User) -> set[RoleSlug]:
    return {role.slug for role in user.roles}


def user_has_role(user: User, role_slug: RoleSlug) -> bool:
    return role_slug in get_user_role_slugs(user)


def require_any_role(user: User, allowed_roles: set[RoleSlug]) -> None:
    if not get_user_role_slugs(user).intersection(allowed_roles):
        allowed = ", ".join(sorted(role.value for role in allowed_roles))
        raise PermissionError(f"User does not have required role. Expected one of: {allowed}")
