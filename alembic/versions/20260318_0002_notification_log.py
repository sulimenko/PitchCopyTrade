"""Add notification_log table.

Revision ID: 20260318_0002
Revises: 20260310_0001
Create Date: 2026-03-18
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260318_0002"
down_revision = "20260310_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Создаём тип отдельно с checkfirst, затем передаём create_type=False в create_table
    # чтобы SQLAlchemy не пытался создать тип повторно внутри CREATE TABLE
    notification_channel_type = sa.Enum("telegram", "email", name="notification_channel")
    notification_channel_type.create(op.get_bind(), checkfirst=True)

    notification_channel = sa.Enum("telegram", "email", name="notification_channel", create_type=False)

    op.create_table(
        "notification_log",
        sa.Column("id", sa.Uuid(as_uuid=False), primary_key=True),
        sa.Column("recommendation_id", sa.Uuid(as_uuid=False), sa.ForeignKey("recommendations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Uuid(as_uuid=False), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel", notification_channel, nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("notification_log")
    op.execute("DROP TYPE IF EXISTS notification_channel")
