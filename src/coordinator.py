"""
CC Expense Coordinator — orchestration engine v2.

State machine per cardholder:
  pending
    → AUTO_APPROVED_RECURRING      (all transactions whitelisted — no email)
    → outreach_sent                (receipt request email sent)
        → APPROVED                 (all validated on first reply — Eric, Todd)
        → AWAITING_RESUBMISSION    (partial fail — Kim, Cory)
            → APPROVED             (all validated on resubmission)
            → MANUAL_REVIEW_REQUIRED  (Cory Bach: deadline passed)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from loguru import logger

from src.excel_parser import Cardholder
from src.whitelist import is_whitelisted
from src.email_templates import (
    build_outreach_email,
    build_success_email,
    build_partial_fail_email,
    build_partial_fail_warning_email,
    build_escalation_notice_email,
)

if TYPE_CHECKING:
    from src.gmail_client import GmailClient
    from src.receipt_validator import ScriptedReceiptValidator

RESUBMIT_WINDOW_MINUTES = 5
TERMINAL_STATES = {"APPROVED", "AUTO_APPROVED_RECURRING", "MANUAL_REVIEW_REQUIRED"}


class ExpenseCoordinator:

    def __init__(
        self,
        gmail: "GmailClient",
        validator: "ScriptedReceiptValidator",
        state_file: str,
    ) -> None:
        self.gmail      = gmail
        self.validator  = validator
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

    # ── Email helper — maintains full References chain ─────────────────────

    def _send_and_track(
        self,
        entry: dict,
        to: str,
        body: str,
        reply_to_mid: str | None = None,
    ) -> str:
        """
        Send an email in the existing thread and update tracking fields.

        Subject is ALWAYS entry['thread_subject'] — the original outreach subject
        prefixed with 'Re:'. This is what keeps all messages in the same Gmail thread.
        Changing the subject mid-thread causes Gmail to split it into a new conversation.

        reply_to_mid: the employee's most recent message ID (In-Reply-To).
        """
        subject = entry.get("thread_subject", "Re: Expense Compensation")

        existing_refs = entry.get("references", entry.get("message_id", ""))
        if reply_to_mid and reply_to_mid not in existing_refs:
            references = f"{existing_refs} {reply_to_mid}".strip()
        else:
            references = existing_refs

        in_reply_to = reply_to_mid or entry.get("last_agent_mid") or entry.get("message_id")

        mid = self.gmail.send_email(
            to=to,
            subject=subject,
            body=body,
            in_reply_to=in_reply_to,
            references=references,
        )
        self.gmail.label_thread([mid])
        entry["last_agent_mid"] = mid
        entry["references"] = f"{references} {mid}".strip()
        return mid

    # ── Outreach pass ──────────────────────────────────────────────────────

    def process_new_statement(self, cardholders: list[Cardholder]) -> None:
        """
        For each cardholder (no idempotency guard — always re-processes):
          1. Split transactions into whitelisted / non-whitelisted.
          2. If ALL whitelisted → AUTO_APPROVED_RECURRING, no email.
          3. Otherwise → send outreach with only non-whitelisted transactions.
        """
        for ch in cardholders:
            non_wl = [tx for tx in ch.transactions if not is_whitelisted(tx.merchant_name)]
            wl     = [tx for tx in ch.transactions if is_whitelisted(tx.merchant_name)]
            wl_names = [tx.merchant_name for tx in wl]

            if not non_wl:
                logger.info(
                    f"{ch.name}: all {len(wl)} transaction(s) auto-approved "
                    f"(whitelist: {', '.join(set(wl_names))})"
                )
                self._state[ch.name] = {
                    "name": ch.name, "email": ch.email,
                    "status": "AUTO_APPROVED_RECURRING",
                    "whitelisted_transactions": wl_names,
                    "transactions": [],
                    "sent_at": datetime.utcnow().isoformat(),
                }
                self._save_state()
                continue

            # Send outreach with only non-whitelisted transactions
            ch_non_wl = Cardholder(
                name=ch.name, email=ch.email, account_number=ch.account_number,
                transactions=non_wl,
            )
            subject, body = build_outreach_email(ch_non_wl)
            mid = self.gmail.send_email(to=ch.email, subject=subject, body=body)
            self.gmail.label_thread([mid])

            self._state[ch.name] = {
                "name": ch.name, "email": ch.email,
                "status": "outreach_sent",
                "message_id": mid,
                "last_agent_mid": mid,
                "last_processed_reply_mid": None,
                "references": mid,
                "thread_subject": f"Re: {subject}",  # ALL future replies use this subject
                "sent_at": datetime.utcnow().isoformat(),
                "reply_count": 0,
                "resubmit_deadline": None,
                "whitelisted_transactions": wl_names,
                "failed_items": [],
                "transactions": [
                    {"merchant_name": tx.merchant_name, "amount": tx.amount}
                    for tx in non_wl
                ],
            }
            self._save_state()

            wl_note = f" ({len(wl)} auto-approved via whitelist)" if wl else ""
            logger.success(f"Outreach sent → {ch.name} <{ch.email}>{wl_note}")

    # ── Reply-poll pass ────────────────────────────────────────────────────

    def check_for_replies(self) -> None:
        """
        Poll for employee replies with attachments.
        Handles outreach_sent and AWAITING_RESUBMISSION states.
        Prevents double-processing the same reply via last_processed_reply_mid.
        """
        for name, entry in list(self._state.items()):
            status = entry.get("status")
            if status not in ("outreach_sent", "AWAITING_RESUBMISSION"):
                continue

            # Search from last agent message so we catch replies to it
            search_mid = entry.get("last_agent_mid") or entry.get("message_id")
            reply_mid  = self.gmail.find_reply_with_attachment(search_mid)

            if not reply_mid:
                continue

            # Skip if we already processed this reply in a previous tick
            if reply_mid == entry.get("last_processed_reply_mid"):
                continue

            entry["reply_count"] = entry.get("reply_count", 0) + 1
            entry["last_processed_reply_mid"] = reply_mid
            reply_count = entry["reply_count"]
            logger.info(f"Reply #{reply_count} detected for {name} (mid={reply_mid})")

            ch_stub = Cardholder(name=name, email=entry["email"], account_number="")

            # ── Deadline check BEFORE validation (Scenario D Branch 2) ─────
            deadline_str = entry.get("resubmit_deadline")
            if deadline_str and status == "AWAITING_RESUBMISSION":
                deadline = datetime.fromisoformat(deadline_str)
                if datetime.utcnow() > deadline:
                    logger.warning(
                        f"{name}: resubmit deadline passed "
                        f"({deadline.isoformat()}) — escalating"
                    )
                    subj, body = build_escalation_notice_email(ch_stub)
                    self._send_and_track(
                        entry, entry["email"],
                        body, reply_to_mid=reply_mid,
                    )
                    entry["status"] = "MANUAL_REVIEW_REQUIRED"
                    self._save_state()
                    logger.warning(f"{name} → MANUAL_REVIEW_REQUIRED")
                    continue

            # ── Scripted validation ────────────────────────────────────────
            result = self.validator.validate(name, reply_count)

            if result.approved:
                subj, body = build_success_email(ch_stub)
                self._send_and_track(
                    entry, entry["email"],
                    body, reply_to_mid=reply_mid,
                )
                entry["status"] = "APPROVED"
                entry["approved_at"] = datetime.utcnow().isoformat()
                self._save_state()
                logger.success(f"{name} → APPROVED")

            else:
                # Partial fail — ask for resubmission
                entry["failed_items"] = result.failed_items

                # Cory Bach reply 2: use warning email + start 5-min deadline
                use_warning = (name == "CORY BACH" and reply_count == 2)
                if use_warning:
                    subj, body = build_partial_fail_warning_email(ch_stub, result.failed_items)
                    deadline = datetime.utcnow() + timedelta(minutes=RESUBMIT_WINDOW_MINUTES)
                    entry["resubmit_deadline"] = deadline.isoformat()
                    logger.info(
                        f"{name}: 5-min deadline set → {deadline.isoformat()}"
                    )
                else:
                    subj, body = build_partial_fail_email(ch_stub, result.failed_items)

                self._send_and_track(
                    entry, entry["email"],
                    body, reply_to_mid=reply_mid,
                )
                entry["status"] = "AWAITING_RESUBMISSION"
                self._save_state()
                logger.info(
                    f"{name} → AWAITING_RESUBMISSION "
                    f"({'with deadline' if use_warning else 'no deadline yet'}, "
                    f"{len(result.failed_items)} item(s) failed)"
                )

    # ── Status helpers ─────────────────────────────────────────────────────

    def all_resolved(self) -> bool:
        if not self._state:
            return False
        return all(e.get("status") in TERMINAL_STATES for e in self._state.values())

    def print_status(self) -> None:
        print(f"\n{'Cardholder':<25} {'Status':<28} {'Info'}")
        print("-" * 85)
        for name, entry in self._state.items():
            status = entry.get("status", "?")
            info = ""
            if status == "AWAITING_RESUBMISSION":
                deadline = entry.get("resubmit_deadline", "")
                info = f"deadline={deadline[:19]}" if deadline else ""
            elif status == "AUTO_APPROVED_RECURRING":
                info = f"whitelist: {len(entry.get('whitelisted_transactions', []))} tx"
            elif status == "APPROVED":
                info = f"approved_at={entry.get('approved_at', '')[:19]}"
            print(f"{name:<25} {status:<28} {info}")
        print()
