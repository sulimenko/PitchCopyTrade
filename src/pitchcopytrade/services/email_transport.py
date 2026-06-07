from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from email.message import EmailMessage

from pitchcopytrade.core.config import get_settings


logger = logging.getLogger(__name__)


async def send_smtp_email(
    *,
    to_email: str | None,
    subject: str,
    body: str,
    bcc_emails: Sequence[str] = (),
) -> tuple[bool, str | None]:
    if not to_email:
        return False, "email not set"

    settings = get_settings()
    smtp_password = settings.notifications.smtp_password.get_secret_value().strip()
    if not smtp_password or smtp_password.startswith("__FILL_ME__"):
        return False, "smtp is not configured"

    try:
        import aiosmtplib

        message = EmailMessage()
        message["From"] = f"{settings.notifications.smtp_from_name} <{settings.notifications.smtp_from}>"
        message["To"] = to_email
        message["Subject"] = subject
        message.set_content(body)

        recipients = [to_email]
        normalized_to = to_email.strip().lower()
        for email in bcc_emails:
            normalized_email = (email or "").strip()
            if not normalized_email:
                continue
            if normalized_email.lower() == normalized_to:
                continue
            recipients.append(normalized_email)

        # BCC is kept out of message headers and only added at the SMTP envelope level.
        await asyncio.wait_for(
            aiosmtplib.send(
                message,
                hostname=settings.notifications.smtp_host,
                port=settings.notifications.smtp_port,
                use_tls=settings.notifications.smtp_ssl,
                username=settings.notifications.smtp_user,
                password=smtp_password,
                recipients=recipients,
            ),
            timeout=10.0,
        )
        return True, None
    except asyncio.TimeoutError:
        logger.warning("SMTP timeout for %s", to_email)
        return False, "smtp timeout"
    except Exception as exc:
        logger.warning("email delivery failed for %s: %s", to_email, exc)
        return False, str(exc)
