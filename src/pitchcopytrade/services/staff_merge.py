from __future__ import annotations

from datetime import datetime

from pitchcopytrade.db.models.accounts import User
from pitchcopytrade.db.models.enums import InviteDeliveryStatus


def apply_staff_surviving_metadata(
    target: User,
    *,
    email: str | None,
    full_name: str | None,
    timezone_name: str | None,
    invite_token_version: int,
    invite_delivery_status: InviteDeliveryStatus | None,
    invite_delivery_error: str | None,
    invite_delivery_updated_at: datetime | None,
) -> None:
    target.email = email
    target.full_name = full_name
    if timezone_name is not None:
        target.timezone = timezone_name
    target.invite_token_version = max(int(invite_token_version or 1), 1)
    target.invite_delivery_status = invite_delivery_status
    target.invite_delivery_error = invite_delivery_error
    target.invite_delivery_updated_at = invite_delivery_updated_at
