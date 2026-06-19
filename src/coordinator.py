"""
Main orchestration loop for the CC Expense Coordinator.

State machine per cardholder (persisted to JSON):
    pending → outreach_sent → approved

Idempotent: any cardholder already past 'pending' is skipped on
process_new_statement(), so the agent can be safely restarted.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import TYPE_CHECKING

from loguru import logger

from src.excel_parser import Cardholder, Transaction
from src.email_templates import build_outreach_email, build_success_email

if TYPE_CHECKING:
    from src.gmail_client import GmailClient
    from src.receipt_validator import MockReceiptValidator


class ExpenseCoordinator:

    def __init__(
        self,
        gmail: "GmailClient",
        validator: "MockReceiptValidator",
        state_file: str,
    ) -> None:
        self.gmail     = gmail
        self.validator = validator
        self.state_file = state_file
        self._state: dict = self._load_state()

    # ── State persistence ──────────────────────────────────────────────────

    def _load_state(self) -> dict:
        if self.state_file == ":memory:" or not os.path.exists(self.state_file):
            return {}
        with open(self.state_file) as f:
            return json.load(f)

    def _save_state(self) -> None:
        if self.state_file == ":memory:":
            return
        os.makedirs(os.path.dirname(os.path.abspath(self.state_file)), exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self._state, f, indent=2, default=str)

    # ── Outreach pass ──────────────────────────────────────────────────────

    def process_new_statement(self, cardholders: list[Cardholder]) -> None:
        """
        For each cardholder not yet contacted:
          1. Draft personalised outreach email (OpenAI).
          2. Send via SMTP.
          3. Label the sent message 'compensation'.
          4. Persist state (status=outreach_sent, message_id stored for reply tracking).
        """
        for ch in cardholders:
            current_status = self._state.get(ch.name, {}).get("status", "pending")
            if current_status != "pending":
                logger.info(f"Skipping {ch.name} — already {current_status}")
                continue

            subject, body = build_outreach_email(ch)
            message_id = self.gmail.send_email(
                to=ch.email, subject=subject, body=body
            )
            # Label the sent message
            self.gmail.label_thread([message_id])

            self._state[ch.name] = {
                "name": ch.name,
                "email": ch.email,
                "status": "outreach_sent",
                "message_id": message_id,      # Message-ID header for reply tracking
                "sent_at": datetime.utcnow().isoformat(),
                "transactions": [
                    {"merchant_name": tx.merchant_name, "amount": tx.amount}
                    for tx in ch.transactions
                ],
            }
            self._save_state()
            logger.success(f"Outreach sent → {ch.name} <{ch.email}>")

    # ── Reply-poll pass ────────────────────────────────────────────────────

    def check_for_replies(self) -> None:
        """
        Poll INBOX for replies with attachments to any outreach_sent thread.
        On detecting an attachment:
          1. Mock-validate (always passes in POC).
          2. Draft and send success email in reply.
          3. Label both messages 'compensation'.
          4. Update status to 'approved'.
        """
        for name, entry in list(self._state.items()):
            if entry.get("status") != "outreach_sent":
                continue

            original_mid = entry["message_id"]

            if not self.gmail.thread_has_reply_with_attachment(original_mid):
                continue

            logger.info(f"Receipt detected for {name}")

            # Mock validation — always approves in POC
            first_tx = entry.get("transactions", [{}])[0]
            mock_tx = Transaction(
                account_name=name, account_number="",
                allocation_code="", posting_date=None,
                amount=float(first_tx.get("amount", 0)),
                merchant_name=first_tx.get("merchant_name", ""),
            )
            result = self.validator.validate(mock_tx, "uploaded_document")
            logger.info(f"Validation [{name}]: {result.reason}")

            # Send success email as a reply in the same thread
            ch_stub = Cardholder(name=name, email=entry["email"], account_number="")
            subject, body = build_success_email(ch_stub)
            success_mid = self.gmail.send_email(
                to=entry["email"],
                subject=subject,
                body=body,
                in_reply_to=original_mid,
                references=original_mid,
            )
            self.gmail.label_thread([success_mid])

            entry["status"] = "approved"
            entry["approved_at"] = datetime.utcnow().isoformat()
            self._save_state()
            logger.success(f"Approved — success email sent to {name}.")

    # ── Helpers ────────────────────────────────────────────────────────────

    def all_resolved(self) -> bool:
        """True when every tracked cardholder is in a terminal state."""
        if not self._state:
            return False
        return all(
            e.get("status") in ("approved", "escalated")
            for e in self._state.values()
        )

    def print_status(self) -> None:
        """Print a human-readable status table."""
        print(f"\n{'Cardholder':<25} {'Status':<16} {'Sent at'}")
        print("-" * 70)
        for name, entry in self._state.items():
            print(
                f"{name:<25} {entry.get('status', '?'):<16} "
                f"{entry.get('sent_at', '—')[:19]}"
            )
        print()
