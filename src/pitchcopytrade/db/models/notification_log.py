from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Enum as SqlEnum, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from pitchcopytrade.db.models.accounts import User
    from pitchcopytrade.db.models.content import Recommendation


class NotificationChannelEnum(str, enum.Enum):
    TELEGRAM = "telegram"
    EMAIL = "email"


class NotificationLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notification_log"

    recommendation_id: Mapped[str | None] = mapped_column(
        ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True
    )
    user_id: Mapped[str | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    channel: Mapped[NotificationChannelEnum] = mapped_column(
        SqlEnum(NotificationChannelEnum, name="notification_channel"), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User | None"] = relationship()
    recommendation: Mapped["Recommendation | None"] = relationship()
