"""
Email templates for the CC Expense Coordinator.
Uses OpenAI gpt-4o-mini to draft outreach and success emails.
"""
from __future__ import annotations

from openai import OpenAI

from src import config
from src.excel_parser import Cardholder

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=config.OPENAI_API_KEY)
    return _client


def _call_openai(system: str, user_prompt: str, max_tokens: int = 400) -> str:
    """Thin wrapper around OpenAI chat completions."""
    resp = _get_client().chat.completions.create(
        model=config.OPENAI_MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user_prompt},
        ],
    )
    return (resp.choices[0].message.content or "").strip()


# ── System prompts ─────────────────────────────────────────────────────────

OUTREACH_SYSTEM = """\
You write clear, professional, friendly emails on behalf of a Finance / AP team.
You are given a list of company credit card transactions that an employee needs
to submit receipts or confirmation documents for.
Write a brief outreach email (under 150 words) asking the employee to reply to
this email with the relevant document(s) attached.
Mention the email is tagged for compensation tracking.
Do NOT include a subject line in the body — body text only.
Sign as "The Finance Team"."""

SUCCESS_SYSTEM = """\
You write warm, concise confirmation emails on behalf of a Finance / AP team.
Tell the employee their receipt / confirmation document has been received and
their expense compensation request has been approved. Keep it under 80 words.
Do NOT include a subject line in the body — body text only.
Sign as "The Finance Team"."""

PARTIAL_FAIL_SYSTEM = """\
You write clear, professional emails on behalf of a Finance / AP team.
The employee submitted receipts but some could not be matched to transactions.
Write a brief email (under 120 words) that:
1. Thanks them for submitting.
2. Lists the specific transactions whose receipts could not be found or parsed.
3. Asks them to reply to THIS email with the missing receipts attached.
Do NOT include a subject line — body only. Sign as "The Finance Team"."""

PARTIAL_FAIL_WARNING_SYSTEM = """\
You write clear, professional emails on behalf of a Finance / AP team.
The employee submitted receipts a second time but some still could not be matched.
Write a brief email (under 140 words) that:
1. Acknowledges this is their second attempt.
2. Lists the specific transactions whose receipts still could not be found or parsed.
3. Clearly states they have 5 minutes to reply with the correct receipts.
4. Warns that if they do not respond within 5 minutes, the case will be escalated to the support team for manual review.
Do NOT include a subject line — body only. Sign as "The Finance Team"."""

ESCALATION_NOTICE_SYSTEM = """\
You write professional, empathetic emails on behalf of a Finance / AP team.
The employee did not resubmit missing receipts within the required timeframe.
Write a brief email (under 80 words) informing them:
1. The resubmission window has passed.
2. Their case has been escalated to the support team for manual review.
3. They may be contacted by the team directly.
Do NOT include a subject line — body only. Sign as "The Finance Team"."""


def build_outreach_email(cardholder: Cardholder) -> tuple[str, str]:
    """Return (subject, body) for the initial receipt-request email."""
    tx_lines = "\n".join(
        f"  • {tx.posting_date.strftime('%Y-%m-%d') if tx.posting_date else 'N/A'}"
        f" | ${tx.amount:.2f} | {tx.merchant_name}"
        for tx in cardholder.transactions
    )
    first_name = cardholder.name.split()[0].capitalize()
    user_prompt = (
        f"Employee first name: {first_name}\n\n"
        f"Transactions requiring receipts/confirmation:\n{tx_lines}"
    )
    body = _call_openai(OUTREACH_SYSTEM, user_prompt, max_tokens=400)
    subject = (
        f"Action Required: Receipt Submission for Credit Card Transactions"
        f" — {cardholder.name}"
    )
    return subject, body


def build_success_email(cardholder: Cardholder) -> tuple[str, str]:
    """Return (subject, body) for the approval confirmation email."""
    first_name = cardholder.name.split()[0].capitalize()
    body = _call_openai(
        SUCCESS_SYSTEM,
        f"Employee first name: {first_name}",
        max_tokens=200,
    )
    subject = f"Expense Approved — Receipt Received for {cardholder.name}"
    return subject, body


def build_partial_fail_email(
    cardholder: Cardholder, failed_items: list[str]
) -> tuple[str, str]:
    """Return (subject, body) for the first partial-fail / resubmission-request email."""
    first_name = cardholder.name.split()[0].capitalize()
    items_block = "\n".join(f"  • {item}" for item in failed_items)
    user_prompt = (
        f"Employee first name: {first_name}\n\n"
        f"Transactions whose receipts could NOT be found or parsed:\n{items_block}"
    )
    body = _call_openai(PARTIAL_FAIL_SYSTEM, user_prompt, max_tokens=400)
    subject = f"Receipt Resubmission Required — {cardholder.name}"
    return subject, body


def build_partial_fail_warning_email(
    cardholder: Cardholder, failed_items: list[str]
) -> tuple[str, str]:
    """
    Return (subject, body) for the second partial-fail email — includes the
    5-minute deadline warning. Used only for Cory Bach after reply 2 fails.
    """
    first_name = cardholder.name.split()[0].capitalize()
    items_block = "\n".join(f"  • {item}" for item in failed_items)
    user_prompt = (
        f"Employee first name: {first_name}\n\n"
        f"Transactions whose receipts STILL could not be found or parsed "
        f"(second attempt):\n{items_block}"
    )
    body = _call_openai(PARTIAL_FAIL_WARNING_SYSTEM, user_prompt, max_tokens=500)
    subject = f"Final Notice: Receipt Resubmission Required — {cardholder.name}"
    return subject, body


def build_escalation_notice_email(cardholder: Cardholder) -> tuple[str, str]:
    """Return (subject, body) for the escalation notice sent to the employee."""
    first_name = cardholder.name.split()[0].capitalize()
    body = _call_openai(
        ESCALATION_NOTICE_SYSTEM,
        f"Employee first name: {first_name}",
        max_tokens=200,
    )
    subject = f"Case Escalated — {cardholder.name}"
    return subject, body
