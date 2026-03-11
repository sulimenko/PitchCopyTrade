from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, Enum as SqlEnum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pitchcopytrade.db.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from pitchcopytrade.db.models.enums import RecommendationKind, RecommendationStatus, TradeSide


class Recommendation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    strategy_id: Mapped[str] = mapped_column(ForeignKey("strategies.id", ondelete="CASCADE"), nullable=False)
    author_id: Mapped[str] = mapped_column(ForeignKey("author_profiles.id", ondelete="CASCADE"), nullable=False)
    moderated_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[RecommendationKind] = mapped_column(
        SqlEnum(RecommendationKind, name="recommendation_kind"),
        nullable=False,
    )
    status: Mapped[RecommendationStatus] = mapped_column(
        SqlEnum(RecommendationStatus, name="recommendation_status"),
        default=RecommendationStatus.DRAFT,
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    thesis: Mapped[str | None] = mapped_column(Text, nullable=True)
    market_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_moderation: Mapped[bool] = mapped_column(default=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    moderation_comment: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecommendationLeg(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_legs"

    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False)
    instrument_id: Mapped[str | None] = mapped_column(ForeignKey("instruments.id", ondelete="SET NULL"), nullable=True)
    side: Mapped[TradeSide | None] = mapped_column(SqlEnum(TradeSide, name="trade_side"), nullable=True)
    entry_from: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    entry_to: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    stop_loss: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit_1: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit_2: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    take_profit_3: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    time_horizon: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class RecommendationAttachment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "recommendation_attachments"

    recommendation_id: Mapped[str] = mapped_column(ForeignKey("recommendations.id", ondelete="CASCADE"), nullable=False)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    storage_provider: Mapped[str] = mapped_column(String(32), default="minio")
    bucket_name: Mapped[str] = mapped_column(String(120), nullable=False)
    object_key: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
