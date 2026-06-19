from unittest.mock import MagicMock, patch
from datetime import datetime

from src.excel_parser import Cardholder, Transaction

CARDHOLDER = Cardholder(
    name="CORY BACH", email="cory@example.com", account_number="**0450",
    transactions=[
        Transaction("CORY BACH", "**0450", "CODE1",
                    datetime(2025, 5, 28), 37.64, "AMERICAN AIR"),
        Transaction("CORY BACH", "**0450", "CODE2",
                    datetime(2025, 5, 29), 893.49, "AVIS.COM"),
    ]
)

MOCK_RESPONSE = MagicMock()
MOCK_RESPONSE.choices = [
    MagicMock(message=MagicMock(content="Mock email body text here."))
]


def _mock_client():
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MOCK_RESPONSE
    return mock_client


def test_outreach_subject_contains_cardholder_name():
    with patch("src.email_templates._get_client", return_value=_mock_client()):
        from src.email_templates import build_outreach_email
        subject, _ = build_outreach_email(CARDHOLDER)
    assert "CORY BACH" in subject


def test_outreach_subject_has_action_required():
    with patch("src.email_templates._get_client", return_value=_mock_client()):
        from src.email_templates import build_outreach_email
        subject, _ = build_outreach_email(CARDHOLDER)
    assert "Action Required" in subject or "Receipt" in subject


def test_outreach_prompt_includes_merchant_and_amount():
    """The user prompt sent to OpenAI must contain transaction data."""
    mock_client = _mock_client()
    with patch("src.email_templates._get_client", return_value=mock_client):
        from src.email_templates import build_outreach_email
        build_outreach_email(CARDHOLDER)

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs.kwargs.get("messages") or call_kwargs.args[0]
    content = str(messages)
    assert "AMERICAN AIR" in content
    assert "37.64" in content


def test_success_subject_contains_approved():
    with patch("src.email_templates._get_client", return_value=_mock_client()):
        from src.email_templates import build_success_email
        subject, _ = build_success_email(CARDHOLDER)
    assert "Approved" in subject or "Receipt" in subject


def test_success_email_returns_tuple():
    with patch("src.email_templates._get_client", return_value=_mock_client()):
        from src.email_templates import build_success_email
        result = build_success_email(CARDHOLDER)
    assert isinstance(result, tuple) and len(result) == 2
