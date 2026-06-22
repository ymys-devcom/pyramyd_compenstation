from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta

from src.excel_parser import Cardholder, Transaction
from src.receipt_validator import ScriptedReceiptValidator


def _make_cardholder(name, email, merchants):
    txs = [
        Transaction(name, "**0000", "CODE", datetime(2025, 6, 1), 100.0, m)
        for m in merchants
    ]
    return Cardholder(name=name, email=email, account_number="**0000", transactions=txs)


def _make_coord(gmail=None, validator=None):
    from src.coordinator import ExpenseCoordinator
    gmail     = gmail     or MagicMock()
    validator = validator or ScriptedReceiptValidator()
    gmail.send_email.return_value = "<mid@example.com>"
    return ExpenseCoordinator(gmail=gmail, validator=validator, state_file=":memory:")


# ── Outreach / whitelist tests ─────────────────────────────────────────────

def test_all_whitelisted_no_email_sent():
    """Cardholder with only AMAZON transactions → AUTO_APPROVED_RECURRING, no email."""
    gmail = MagicMock()
    coord = _make_coord(gmail=gmail)
    ch = _make_cardholder("TEST", "t@x.com", ["AMAZON MKTPL*ABC", "AMAZON MKTPL*XYZ"])
    with patch("src.coordinator.build_outreach_email"):
        coord.process_new_statement([ch])
    gmail.send_email.assert_not_called()
    assert coord._state["TEST"]["status"] == "AUTO_APPROVED_RECURRING"


def test_mixed_whitelist_outreach_only_non_whitelisted():
    """Mixed cardholder: outreach sent, only non-AMAZON transactions in email."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<mid@example.com>"
    coord = _make_coord(gmail=gmail)
    ch = _make_cardholder("TODD BAHR", "todd@x.com", [
        "AMAZON MKTPL*NQ10Q3GX2", "LOWES #01023*", "HARBOR FREIGHT TOOLS3249"
    ])
    captured_ch = []
    with patch("src.coordinator.build_outreach_email",
               side_effect=lambda c: (captured_ch.append(c), ("Subj", "Body"))[1]):
        coord.process_new_statement([ch])

    # Only 2 non-AMAZON merchants passed to email template
    assert len(captured_ch[0].transactions) == 2
    merchants = [tx.merchant_name for tx in captured_ch[0].transactions]
    assert "LOWES #01023*" in merchants
    assert "HARBOR FREIGHT TOOLS3249" in merchants
    assert "AMAZON MKTPL*NQ10Q3GX2" not in merchants


def test_outreach_always_sent_no_idempotency_skip():
    """Even if cardholder already processed, always re-sends on new file."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<mid@example.com>"
    coord = _make_coord(gmail=gmail)
    coord._state["ERIC WILSON"] = {"status": "APPROVED", "email": "e@x.com"}
    ch = _make_cardholder("ERIC WILSON", "e@x.com", ["BOWL OF PHO"])
    with patch("src.coordinator.build_outreach_email", return_value=("S", "B")):
        coord.process_new_statement([ch])
    gmail.send_email.assert_called_once()


# ── Reply / approval tests ─────────────────────────────────────────────────

def test_eric_wilson_reply1_approved():
    """Scenario A: Eric Wilson, reply 1 → APPROVED."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<approval@example.com>"
    gmail.find_reply_with_attachment.return_value = "<reply1@employee.com>"
    coord = _make_coord(gmail=gmail)
    coord._state = {"ERIC WILSON": {
        "status": "outreach_sent", "email": "e@x.com", "name": "ERIC WILSON",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": None, "references": "<mid@x.com>",
        "reply_count": 0, "resubmit_deadline": None, "transactions": [], "failed_items": [],
    }}
    with patch("src.coordinator.build_success_email", return_value=("Approved", "Body")):
        coord.check_for_replies()
    assert coord._state["ERIC WILSON"]["status"] == "APPROVED"


def test_kim_watroba_partial_fail_then_approved():
    """Scenario C: Kim Watroba, reply 1 → AWAITING_RESUBMISSION, reply 2 → APPROVED."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<agent@x.com>"
    coord = _make_coord(gmail=gmail)
    coord._state = {"KIM WATROBA": {
        "status": "outreach_sent", "email": "k@x.com", "name": "KIM WATROBA",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": None, "references": "<mid@x.com>",
        "reply_count": 0, "resubmit_deadline": None, "transactions": [], "failed_items": [],
    }}

    # Reply 1 — partial fail
    gmail.find_reply_with_attachment.return_value = "<reply1@k.com>"
    with patch("src.coordinator.build_partial_fail_email", return_value=("Resubmit", "Body")):
        coord.check_for_replies()
    assert coord._state["KIM WATROBA"]["status"] == "AWAITING_RESUBMISSION"
    assert "SCREAMING FROG LTD" in coord._state["KIM WATROBA"]["failed_items"]

    # Reply 2 — approved
    gmail.find_reply_with_attachment.return_value = "<reply2@k.com>"
    with patch("src.coordinator.build_success_email", return_value=("Approved", "Body")):
        coord.check_for_replies()
    assert coord._state["KIM WATROBA"]["status"] == "APPROVED"


def test_cory_bach_reply2_sets_deadline_and_sends_warning():
    """Scenario D: reply 2 → partial fail again + 5-min deadline set + warning email."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<agent@x.com>"
    coord = _make_coord(gmail=gmail)
    coord._state = {"CORY BACH": {
        "status": "AWAITING_RESUBMISSION", "email": "c@x.com", "name": "CORY BACH",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": "<reply1@c.com>",
        "references": "<mid@x.com>", "reply_count": 1,
        "resubmit_deadline": None,   # no deadline yet after reply 1
        "thread_subject": "Re: Action Required",
        "transactions": [], "failed_items": [],
    }}
    gmail.find_reply_with_attachment.return_value = "<reply2@c.com>"
    with patch("src.coordinator.build_partial_fail_warning_email",
               return_value=("Warning", "Body with warning")):
        coord.check_for_replies()

    assert coord._state["CORY BACH"]["status"] == "AWAITING_RESUBMISSION"
    assert coord._state["CORY BACH"]["resubmit_deadline"] is not None  # deadline now set
    assert coord._state["CORY BACH"]["reply_count"] == 2


def test_cory_bach_within_deadline_approved():
    """Scenario D Branch 1: reply 3 within deadline → APPROVED."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<agent@x.com>"
    coord = _make_coord(gmail=gmail)
    future = (datetime.utcnow() + timedelta(minutes=10)).isoformat()
    coord._state = {"CORY BACH": {
        "status": "AWAITING_RESUBMISSION", "email": "c@x.com", "name": "CORY BACH",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": "<reply2@c.com>",
        "references": "<mid@x.com>", "reply_count": 2,
        "resubmit_deadline": future,
        "thread_subject": "Re: Action Required",
        "transactions": [], "failed_items": [],
    }}
    gmail.find_reply_with_attachment.return_value = "<reply3@c.com>"
    with patch("src.coordinator.build_success_email", return_value=("Approved", "Body")):
        coord.check_for_replies()
    assert coord._state["CORY BACH"]["status"] == "APPROVED"


def test_cory_bach_past_deadline_escalated():
    """Scenario D Branch 2: reply 3 after deadline → MANUAL_REVIEW_REQUIRED."""
    gmail = MagicMock()
    gmail.send_email.return_value = "<agent@x.com>"
    coord = _make_coord(gmail=gmail)
    past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    coord._state = {"CORY BACH": {
        "status": "AWAITING_RESUBMISSION", "email": "c@x.com", "name": "CORY BACH",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": "<reply2@c.com>",
        "references": "<mid@x.com>", "reply_count": 2,
        "resubmit_deadline": past,
        "thread_subject": "Re: Action Required",
        "transactions": [], "failed_items": [],
    }}
    gmail.find_reply_with_attachment.return_value = "<reply3@c.com>"
    with patch("src.coordinator.build_escalation_notice_email",
               return_value=("Escalated", "Body")):
        coord.check_for_replies()
    assert coord._state["CORY BACH"]["status"] == "MANUAL_REVIEW_REQUIRED"


def test_same_reply_not_processed_twice():
    """last_processed_reply_mid prevents double-processing the same reply."""
    gmail = MagicMock()
    gmail.find_reply_with_attachment.return_value = "<reply1@x.com>"
    coord = _make_coord(gmail=gmail)
    coord._state = {"ERIC WILSON": {
        "status": "outreach_sent", "email": "e@x.com", "name": "ERIC WILSON",
        "message_id": "<mid@x.com>", "last_agent_mid": "<mid@x.com>",
        "last_processed_reply_mid": "<reply1@x.com>",  # already processed
        "references": "<mid@x.com>", "reply_count": 1,
        "resubmit_deadline": None, "transactions": [], "failed_items": [],
    }}
    coord.check_for_replies()
    gmail.send_email.assert_not_called()


def test_all_resolved_with_mixed_terminal_states():
    coord = _make_coord()
    coord._state = {
        "A": {"status": "APPROVED"},
        "B": {"status": "AUTO_APPROVED_RECURRING"},
        "C": {"status": "MANUAL_REVIEW_REQUIRED"},
    }
    assert coord.all_resolved() is True


def test_not_resolved_while_awaiting():
    coord = _make_coord()
    coord._state = {
        "A": {"status": "APPROVED"},
        "B": {"status": "AWAITING_RESUBMISSION"},
    }
    assert coord.all_resolved() is False
