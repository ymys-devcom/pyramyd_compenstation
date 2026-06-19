from unittest.mock import MagicMock, patch
from datetime import datetime

from src.excel_parser import Cardholder, Transaction

CARDHOLDER = Cardholder(
    name="TEST USER", email="test@example.com", account_number="**9999",
    transactions=[
        Transaction("TEST USER", "**9999", "CODE1",
                    datetime(2025, 6, 1), 100.0, "ACME CORP")
    ],
)


def _make_coord(gmail=None, validator=None):
    from src.coordinator import ExpenseCoordinator
    gmail     = gmail     or MagicMock()
    validator = validator or MagicMock()
    gmail.send_email.return_value = "<msg_001@example.com>"
    return ExpenseCoordinator(gmail=gmail, validator=validator, state_file=":memory:")


def test_process_statement_sends_outreach_email():
    coord = _make_coord()
    with patch("src.coordinator.build_outreach_email", return_value=("Subj", "Body")):
        coord.process_new_statement([CARDHOLDER])
    coord.gmail.send_email.assert_called_once_with(
        to="test@example.com", subject="Subj", body="Body"
    )


def test_process_statement_labels_message():
    coord = _make_coord()
    with patch("src.coordinator.build_outreach_email", return_value=("S", "B")):
        coord.process_new_statement([CARDHOLDER])
    coord.gmail.label_thread.assert_called_once_with(["<msg_001@example.com>"])


def test_process_statement_saves_state():
    coord = _make_coord()
    with patch("src.coordinator.build_outreach_email", return_value=("S", "B")):
        coord.process_new_statement([CARDHOLDER])
    assert coord._state["TEST USER"]["status"] == "outreach_sent"
    assert coord._state["TEST USER"]["message_id"] == "<msg_001@example.com>"


def test_process_statement_skips_already_sent():
    coord = _make_coord()
    coord._state["TEST USER"] = {
        "status": "outreach_sent", "message_id": "<m1@x.com>",
        "email": "test@example.com", "name": "TEST USER",
        "sent_at": "2025-06-01T00:00:00", "transactions": [],
    }
    coord.process_new_statement([CARDHOLDER])
    coord.gmail.send_email.assert_not_called()


def test_check_replies_sends_success_on_attachment():
    gmail     = MagicMock()
    validator = MagicMock()
    gmail.thread_has_reply_with_attachment.return_value = True
    gmail.send_email.return_value = "<msg_002@example.com>"
    validator.validate.return_value = MagicMock(approved=True, reason="OK")

    coord = _make_coord(gmail=gmail, validator=validator)
    coord._state = {
        "TEST USER": {
            "status": "outreach_sent", "message_id": "<msg_001@example.com>",
            "email": "test@example.com", "name": "TEST USER",
            "sent_at": "2025-06-01T00:00:00",
            "transactions": [{"merchant_name": "ACME CORP", "amount": 100.0}],
        }
    }
    with patch("src.coordinator.build_success_email",
               return_value=("Approved", "Your expense is approved.")):
        coord.check_for_replies()

    gmail.send_email.assert_called_once()
    assert coord._state["TEST USER"]["status"] == "approved"


def test_check_replies_does_nothing_without_attachment():
    gmail = MagicMock()
    gmail.thread_has_reply_with_attachment.return_value = False

    coord = _make_coord(gmail=gmail)
    coord._state = {
        "TEST USER": {
            "status": "outreach_sent", "message_id": "<m1@x.com>",
            "email": "test@example.com", "name": "TEST USER",
            "sent_at": "2025-06-01T00:00:00", "transactions": [],
        }
    }
    coord.check_for_replies()
    gmail.send_email.assert_not_called()


def test_all_resolved_false_when_pending():
    coord = _make_coord()
    coord._state = {"A": {"status": "outreach_sent"}}
    assert coord.all_resolved() is False


def test_all_resolved_true_when_all_approved():
    coord = _make_coord()
    coord._state = {
        "A": {"status": "approved"},
        "B": {"status": "approved"},
    }
    assert coord.all_resolved() is True
