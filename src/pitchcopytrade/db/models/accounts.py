from __future__ import annotations

from sqlalchemy import BigInteger, Column, Enum as SqlEnum, ForeignKey, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from pitchcopytrade.db.models.enums import RoleSlug, UserStatus

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        UniqueConstraint("telegram_user_id", name="uq_users_telegram_user_id"),
    )

    email: Mapped[str | None] = mapped_column(String(320), nullable=True, index=True)
    telegram_user_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    full_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[UserStatus] = mapped_column(SqlEnum(UserStatus, name="user_status"), default=UserStatus.ACTIVE)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Moscow")
    lead_source_id: Mapped[str | None] = mapped_column(ForeignKey("lead_sources.id", ondelete="SET NULL"), nullable=True)

    roles: Mapped[list["Role"]] = relationship(secondary=user_roles, back_populates="users")
    author_profile: Mapped["AuthorProfile | None"] = relationship(back_populates="user", uselist=False)


class Role(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "roles"

    slug: Mapped[RoleSlug] = mapped_column(SqlEnum(RoleSlug, name="role_slug"), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(120), nullable=False)

    users: Mapped[list[User]] = relationship(secondary=user_roles, back_populates="roles")


class AuthorProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "author_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_author_profiles_user_id"),
        UniqueConstraint("slug", name="uq_author_profiles_slug"),
    )

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_moderation: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)

    user: Mapped[User] = relationship(back_populates="author_profile")
