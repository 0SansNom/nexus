"""IMAP client for reading emails."""

import email
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from email.header import decode_header
from email.utils import parsedate_to_datetime
from imaplib import IMAP4_SSL
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Email:
    """Parsed email message."""

    uid: str
    subject: str
    sender: str
    sender_email: str
    recipients: list[str]
    date: datetime
    body_text: str
    body_html: str | None
    attachments: list[dict[str, Any]]
    folder: str
    flags: list[str]


class IMAPClient:
    """IMAP client for reading emails with timeout handling."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        username: str | None = None,
        password: str | None = None,
    ):
        self.host = host or os.getenv("IMAP_HOST", "")
        self.port = port or int(os.getenv("IMAP_PORT", "993"))
        self.username = username or os.getenv("EMAIL_USERNAME", "")
        self.password = password or os.getenv("EMAIL_PASSWORD", "")
        self._client: IMAP4_SSL | None = None
        self._timeout = 30

    def connect(self) -> None:
        """Connect to IMAP server."""
        try:
            self._client = IMAP4_SSL(self.host, self.port, timeout=self._timeout)
            self._client.login(self.username, self.password)
            logger.info(f"Connected to IMAP server: {self.host}")
        except Exception as e:
            logger.error(f"Failed to connect to IMAP: {e}")
            raise

    def disconnect(self) -> None:
        """Disconnect from IMAP server."""
        if self._client:
            try:
                self._client.logout()
            except Exception:
                pass
            self._client = None

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    def list_folders(self) -> list[str]:
        """List all mail folders."""
        if not self._client:
            raise RuntimeError("Not connected")

        status, folders = self._client.list()
        if status != "OK":
            return []

        result = []
        for folder in folders:
            if isinstance(folder, bytes):
                parts = folder.decode().split(' "/" ')
                if len(parts) >= 2:
                    result.append(parts[-1].strip('"'))
        return result

    def select_folder(self, folder: str = "INBOX") -> int:
        """Select a folder and return message count."""
        if not self._client:
            raise RuntimeError("Not connected")

        status, data = self._client.select(folder)
        if status != "OK":
            raise RuntimeError(f"Failed to select folder: {folder}")

        return int(data[0])

    def search(
        self,
        folder: str = "INBOX",
        criteria: str = "ALL",
        limit: int | None = None,
    ) -> list[str]:
        """Search for emails matching criteria."""
        if not self._client:
            raise RuntimeError("Not connected")

        self.select_folder(folder)
        status, data = self._client.uid("search", None, criteria)

        if status != "OK":
            return []

        uids = data[0].split()
        if limit:
            uids = uids[-limit:]

        return [uid.decode() for uid in uids]

    def fetch(self, uid: str, folder: str = "INBOX", ensure_folder_selected: bool = True) -> Email | None:
        """Fetch a single email by UID."""
        if not self._client:
            raise RuntimeError("Not connected")

        if ensure_folder_selected:
            self.select_folder(folder)
            
        status, data = self._client.uid("fetch", uid, "(RFC822 FLAGS)")

        if status != "OK" or not data or not data[0]:
            return None

        raw_email = data[0][1]
        flags_data = data[0][0].decode() if isinstance(data[0][0], bytes) else str(data[0][0])

        # Parse flags
        flags = []
        if "\\Seen" in flags_data:
            flags.append("seen")
        if "\\Flagged" in flags_data:
            flags.append("flagged")
        if "\\Answered" in flags_data:
            flags.append("answered")

        # Parse email
        msg = email.message_from_bytes(raw_email)

        return self._parse_email(msg, uid, folder, flags)

    def fetch_many(
        self,
        folder: str = "INBOX",
        limit: int = 10,
        criteria: str = "ALL",
    ) -> list[Email]:
        """Fetch multiple emails from a folder."""
        # Ensure folder is selected once
        self.select_folder(folder)
        
        # Search without re-selecting (though search does select, we can optimize search too if needed, 
        # but for now let's focus on the loop)
        # Actually search calls select_folder, so let's leave that.
        uids = self.search(folder, criteria, limit)
        emails = []

        for uid in uids:
            # Pass ensure_folder_selected=False since we know we are in the right folder
            email_obj = self.fetch(uid, folder, ensure_folder_selected=False)
            if email_obj:
                emails.append(email_obj)

        return emails

    def _parse_email(
        self,
        msg: email.message.Message,
        uid: str,
        folder: str,
        flags: list[str],
    ) -> Email:
        """Parse an email message."""
        # Subject
        subject = self._decode_header(msg.get("Subject", ""))

        # Sender
        from_header = msg.get("From", "")
        sender_name, sender_email = self._parse_address(from_header)

        # Recipients
        to_header = msg.get("To", "")
        recipients = [addr.strip() for addr in to_header.split(",") if addr.strip()]

        # Date
        date_str = msg.get("Date", "")
        try:
            date = parsedate_to_datetime(date_str)
        except Exception:
            date = datetime.now()

        # Body
        body_text = ""
        body_html = None
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition", ""))

                if "attachment" in content_disposition:
                    filename = part.get_filename()
                    if filename:
                        attachments.append({
                            "filename": self._decode_header(filename),
                            "content_type": content_type,
                            "size": len(part.get_payload(decode=True) or b""),
                        })
                elif content_type == "text/plain":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_text = payload.decode(errors="replace")
                elif content_type == "text/html":
                    payload = part.get_payload(decode=True)
                    if payload:
                        body_html = payload.decode(errors="replace")
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                body_text = payload.decode(errors="replace")

        return Email(
            uid=uid,
            subject=subject,
            sender=sender_name or sender_email,
            sender_email=sender_email,
            recipients=recipients,
            date=date,
            body_text=body_text,
            body_html=body_html,
            attachments=attachments,
            folder=folder,
            flags=flags,
        )

    def _decode_header(self, header: str) -> str:
        """Decode an email header."""
        if not header:
            return ""

        decoded_parts = decode_header(header)
        result = []

        for content, charset in decoded_parts:
            if isinstance(content, bytes):
                result.append(content.decode(charset or "utf-8", errors="replace"))
            else:
                result.append(content)

        return "".join(result)

    def _parse_address(self, address: str) -> tuple[str, str]:
        """Parse an email address into name and email."""
        address = self._decode_header(address)

        if "<" in address and ">" in address:
            name = address.split("<")[0].strip().strip('"')
            email_addr = address.split("<")[1].split(">")[0]
            return name, email_addr

        return "", address.strip()

    def mark_read(self, uid: str, folder: str = "INBOX") -> bool:
        """Mark an email as read."""
        if not self._client:
            raise RuntimeError("Not connected")

        self.select_folder(folder)
        status, _ = self._client.uid("store", uid, "+FLAGS", "\\Seen")
        return status == "OK"

    def archive(self, uid: str, folder: str = "INBOX", archive_folder: str = "Archive") -> bool:
        """Archive an email by moving it to archive folder."""
        if not self._client:
            raise RuntimeError("Not connected")

        self.select_folder(folder)

        # Copy to archive
        status, _ = self._client.uid("copy", uid, archive_folder)
        if status != "OK":
            return False

        # Mark as deleted in original folder
        status, _ = self._client.uid("store", uid, "+FLAGS", "\\Deleted")
        if status != "OK":
            return False

        # Expunge deleted messages
        self._client.expunge()
        return True

    def delete(self, uid: str, folder: str = "INBOX") -> bool:
        """Delete an email."""
        if not self._client:
            raise RuntimeError("Not connected")

        self.select_folder(folder)
        status, _ = self._client.uid("store", uid, "+FLAGS", "\\Deleted")
        if status == "OK":
            self._client.expunge()
            return True
        return False
