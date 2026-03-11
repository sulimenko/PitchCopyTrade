from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import Uuid

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from pitchcopytrade.db.models.accounts import User


class AuditEvent(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"

    actor_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(120), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(Uuid(as_uuid=False), nullable=True)
    action: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    actor_user: Mapped["User | None"] = relationship(back_populates="audit_events")
