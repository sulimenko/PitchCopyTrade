from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from pitchcopytrade.db.models.base import Base, utc_now

if TYPE_CHECKING:
    from pitchcopytrade.db.models.accounts import AuthorProfile, User
    from pitchcopytrade.db.models.catalog import Bundle, Strategy


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(Uuid(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    thread: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    parent: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)

    author_id: Mapped[str | None] = mapped_column("author", ForeignKey("author_profiles.id", ondelete="SET NULL"), nullable=True)
    user_id: Mapped[str | None] = mapped_column("user", ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    moderator_id: Mapped[str | None] = mapped_column("moderator", ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    strategy_id: Mapped[str | None] = mapped_column("strategy", ForeignKey("strategies.id", ondelete="SET NULL"), nullable=True)
    bundle_id: Mapped[str | None] = mapped_column("bundle", ForeignKey("bundles.id", ondelete="SET NULL"), nullable=True)

    deliver: Mapped[list[str]] = mapped_column(ARRAY(String(32)), default=list, nullable=False)
    channel: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)),
        default=lambda: ["telegram", "miniapp"],
        nullable=False,
    )

    kind: Mapped[str | None] = mapped_column(String(32), nullable=True)
    type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    moderation: Mapped[str] = mapped_column(String(32), default="required", nullable=False)

    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    schedule: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list, nullable=False)
    text: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict, nullable=False)
    deals: Mapped[list[dict[str, object]]] = mapped_column(JSONB, default=list, nullable=False)

    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    author: Mapped["AuthorProfile | None"] = relationship(back_populates="messages", foreign_keys=[author_id])
    user: Mapped["User | None"] = relationship(back_populates="messages", foreign_keys=[user_id])
    moderator: Mapped["User | None"] = relationship(back_populates="moderated_messages", foreign_keys=[moderator_id])
    strategy: Mapped["Strategy | None"] = relationship(back_populates="messages", foreign_keys=[strategy_id])
    bundle: Mapped["Bundle | None"] = relationship(back_populates="messages", foreign_keys=[bundle_id])
