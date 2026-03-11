"""SMTP client for sending emails."""

import logging
import os
import smtplib
from dataclasses import dataclass
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


@dataclass
class EmailDraft:
    """Email draft to send."""

    to: list[str]
    subject: str
    body_text: str
    body_html: str | None = None
    cc: list[str] | None = None
    bcc: list[str] | None = None
    reply_to: str | None = None
    in_reply_to: str | None = None


class SMTPClient:
    """SMTP client for sending emails with timeout handling."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
    ):
        self.host = host or os.getenv("SMTP_HOST", "")
        self.port = port or int(os.getenv("SMTP_PORT", "587"))
        self.username = username or os.getenv("EMAIL_USERNAME", "")
        self.password = password or os.getenv("EMAIL_PASSWORD", "")
        self.use_tls = use_tls
        self.from_address = os.getenv("EMAIL_FROM", self.username)
        self._timeout = 30

    def send(self, draft: EmailDraft) -> bool:
        """Send an email."""
        try:
            msg = self._build_message(draft)

            with smtplib.SMTP(self.host, self.port, timeout=self._timeout) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)

                recipients = list(draft.to)
                if draft.cc:
                    recipients.extend(draft.cc)
                if draft.bcc:
                    recipients.extend(draft.bcc)

                server.sendmail(self.from_address, recipients, msg.as_string())

            logger.info(f"Email sent to {draft.to}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def _build_message(self, draft: EmailDraft) -> MIMEMultipart:
        """Build a MIME message from a draft."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = draft.subject
        msg["From"] = self.from_address
        msg["To"] = ", ".join(draft.to)

        if draft.cc:
            msg["Cc"] = ", ".join(draft.cc)

        if draft.reply_to:
            msg["Reply-To"] = draft.reply_to

        if draft.in_reply_to:
            msg["In-Reply-To"] = draft.in_reply_to
            msg["References"] = draft.in_reply_to

        # Attach plain text
        msg.attach(MIMEText(draft.body_text, "plain"))

        # Attach HTML if provided
        if draft.body_html:
            msg.attach(MIMEText(draft.body_html, "html"))

        return msg

    def test_connection(self) -> bool:
        """Test SMTP connection."""
        try:
            with smtplib.SMTP(self.host, self.port, timeout=self._timeout) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
            return True
        except Exception as e:
            logger.error(f"SMTP connection test failed: {e}")
            return False
