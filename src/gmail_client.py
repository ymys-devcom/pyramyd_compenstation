"""
Gmail client using SMTP (send) + IMAP (receive).
No Google Cloud project or OAuth required — only an App Password.

Setup (one-time, ~30 seconds):
  1. Go to myaccount.google.com → Security → 2-Step Verification → enable it
  2. Go to myaccount.google.com → Security → App Passwords
  3. Create a new App Password (name it anything, e.g. "cc-agent")
  4. Copy the 16-character password into .env as GMAIL_APP_PASSWORD

For Google Workspace accounts, a Workspace admin may need to enable
"Allow users to manage their access to less secure apps" or App Passwords
under Admin console → Security → Less secure apps.
"""
from __future__ import annotations

import email as email_lib
import imaplib
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from loguru import logger

from src import config


class GmailClient:
    """
    SMTP for sending, IMAP for reply detection.
    Manages a persistent IMAP connection with auto-reconnect.
    """

    def __init__(self) -> None:
        self._imap: Optional[imaplib.IMAP4_SSL] = None

    # ── SMTP send ─────────────────────────────────────────────────────────

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        in_reply_to: Optional[str] = None,
        references: Optional[str] = None,
    ) -> str:
        """
        Send a plain-text email via SMTP.
        Returns the Message-ID of the sent message (used for threading).

        When in_reply_to is provided, Gmail threads the reply correctly.
        """
        msg = MIMEMultipart()
        msg["From"]    = config.GMAIL_ADDRESS
        msg["To"]      = to
        msg["Subject"] = subject

        # Threading headers — keeps replies in the same Gmail thread
        if in_reply_to:
            msg["In-Reply-To"] = in_reply_to
            msg["References"]  = references or in_reply_to

        # Stable Message-ID we generate ourselves so we can track it
        import uuid
        domain = config.GMAIL_ADDRESS.split("@")[-1]
        message_id = f"<{uuid.uuid4().hex}@{domain}>"
        msg["Message-ID"] = message_id

        msg.attach(MIMEText(body, "plain", "utf-8"))

        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
            smtp.sendmail(config.GMAIL_ADDRESS, to, msg.as_bytes())

        logger.info(f"Sent → {to} | subject='{subject[:60]}' | id={message_id}")
        return message_id

    # ── IMAP helpers ──────────────────────────────────────────────────────

    def _connect_imap(self) -> imaplib.IMAP4_SSL:
        """Return a live IMAP connection, reconnecting if needed."""
        if self._imap is not None:
            try:
                self._imap.noop()
                return self._imap
            except Exception:
                self._imap = None

        imap = imaplib.IMAP4_SSL(config.IMAP_HOST, config.IMAP_PORT)
        imap.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        self._imap = imap
        return imap

    def _ensure_label(self) -> None:
        """Create the 'compensation' label/folder in Gmail if it doesn't exist."""
        imap = self._connect_imap()
        label = config.GMAIL_COMPENSATION_LABEL
        status, folders = imap.list()
        existing = []
        if status == "OK" and folders:
            for f in folders:
                if f:
                    decoded = f.decode() if isinstance(f, bytes) else f
                    existing.append(decoded)
        already_exists = any(f'"{label}"' in e or f" {label}" in e for e in existing)
        if not already_exists:
            imap.create(label)
            logger.info(f"Created Gmail label/folder '{label}'")

    def label_thread(self, message_ids: list[str]) -> None:
        """
        Copy messages (by Message-ID header) to the 'compensation' label folder.
        Gmail stores labels as IMAP folders; copying puts the message in that label.
        """
        self._ensure_label()
        imap = self._connect_imap()
        label = config.GMAIL_COMPENSATION_LABEL
        imap.select("INBOX")
        for mid in message_ids:
            # Search by Message-ID header
            search_id = mid.strip("<>")
            status, data = imap.search(None, f'HEADER Message-ID "{search_id}"')
            if status != "OK" or not data[0]:
                # Try with angle brackets
                status, data = imap.search(None, f'HEADER Message-ID "{mid}"')
            if status == "OK" and data[0]:
                for num in data[0].split():
                    try:
                        imap.copy(num, label)
                    except Exception as exc:
                        logger.warning(f"Could not label message {mid}: {exc}")
        logger.debug(f"Labelled {len(message_ids)} message(s) → '{label}'")

    def find_reply_with_attachment(
        self, original_message_id: str
    ) -> Optional[str]:
        """
        Search INBOX for a reply to original_message_id that has an attachment.

        Returns the reply's own Message-ID if found, or None if not found yet.

        Returning the reply Message-ID (not just True/False) lets the coordinator
        pass it as In-Reply-To on the approval email — so the approval lands in
        the employee's existing thread, not as a new separate email.
        """
        imap = self._connect_imap()
        imap.select("INBOX")

        clean_id = original_message_id.strip("<>")
        search_queries = [
            f'HEADER In-Reply-To "{original_message_id}"',
            f'HEADER In-Reply-To "{clean_id}"',
            f'HEADER References "{clean_id}"',
        ]

        found_uids: set[bytes] = set()
        for query in search_queries:
            try:
                status, data = imap.search(None, query)
                if status == "OK" and data[0]:
                    for uid in data[0].split():
                        found_uids.add(uid)
            except Exception:
                pass

        if not found_uids:
            return None

        for uid in found_uids:
            status, msg_data = imap.fetch(uid, "(RFC822)")
            if status != "OK" or not msg_data:
                continue
            for part in msg_data:
                if not isinstance(part, tuple):
                    continue
                msg = email_lib.message_from_bytes(part[1])
                for payload_part in msg.walk():
                    content_disposition = payload_part.get_content_disposition() or ""
                    filename = payload_part.get_filename()
                    if filename or "attachment" in content_disposition:
                        reply_mid = msg.get("Message-ID", "").strip()
                        logger.info(
                            f"Found attachment '{filename}' in reply "
                            f"(reply_mid={reply_mid})"
                        )
                        # Fall back to original if reply has no Message-ID header
                        return reply_mid or original_message_id

        return None

    def thread_has_reply_with_attachment(self, original_message_id: str) -> bool:
        """Backward-compatible wrapper used by unit tests."""
        return self.find_reply_with_attachment(original_message_id) is not None

    def close(self) -> None:
        """Clean up IMAP connection."""
        if self._imap:
            try:
                self._imap.logout()
            except Exception:
                pass
            self._imap = None
