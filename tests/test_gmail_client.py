from unittest.mock import MagicMock, patch
from src.gmail_client import GmailClient


def _make_client():
    """Build a GmailClient with mocked SMTP/IMAP — no real connections."""
    client = GmailClient.__new__(GmailClient)
    client._imap = None
    return client


def test_send_email_returns_message_id():
    client = _make_client()
    mock_smtp = MagicMock()
    with patch("src.gmail_client.smtplib.SMTP") as mock_smtp_cls, \
         patch("src.gmail_client.config.GMAIL_ADDRESS", "agent@example.com"), \
         patch("src.gmail_client.config.GMAIL_APP_PASSWORD", "fake-pass"), \
         patch("src.gmail_client.config.SMTP_HOST", "smtp.gmail.com"), \
         patch("src.gmail_client.config.SMTP_PORT", 587):
        mock_smtp_cls.return_value.__enter__ = lambda s: mock_smtp
        mock_smtp_cls.return_value.__exit__  = MagicMock(return_value=False)
        mock_smtp.sendmail = MagicMock()
        result = client.send_email("to@example.com", "Subject", "Body")

    assert result.startswith("<") and result.endswith(">")


def test_thread_has_reply_with_attachment_true():
    """IMAP returns a message with an attachment — should return True."""
    import email as email_lib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    # Build a fake reply email with a PDF attachment
    msg = MIMEMultipart()
    msg["In-Reply-To"] = "<original@example.com>"
    msg["References"]  = "<original@example.com>"
    msg.attach(MIMEText("Here is my receipt", "plain"))

    attachment = MIMEBase("application", "pdf")
    attachment.set_payload(b"%PDF fake")
    encoders.encode_base64(attachment)
    attachment.add_header("Content-Disposition", "attachment", filename="receipt.pdf")
    msg.attach(attachment)

    raw = msg.as_bytes()

    client = _make_client()
    mock_imap = MagicMock()
    mock_imap.search.return_value = ("OK", [b"1"])
    mock_imap.fetch.return_value  = ("OK", [(b"1 (RFC822 {100})", raw)])
    mock_imap.noop.return_value   = ("OK", [])
    client._imap = mock_imap

    with patch("src.gmail_client.config.IMAP_HOST", "imap.gmail.com"), \
         patch("src.gmail_client.config.IMAP_PORT", 993):
        result = client.thread_has_reply_with_attachment("<original@example.com>")

    assert result is True


def test_thread_has_reply_with_no_attachment_false():
    """IMAP returns a plain-text reply with no attachment — should return False."""
    import email as email_lib
    from email.mime.text import MIMEText

    msg = MIMEText("I'll send the receipt later.")
    msg["In-Reply-To"] = "<original@example.com>"
    raw = msg.as_bytes()

    client = _make_client()
    mock_imap = MagicMock()
    mock_imap.search.return_value = ("OK", [b"1"])
    mock_imap.fetch.return_value  = ("OK", [(b"1 (RFC822 {50})", raw)])
    mock_imap.noop.return_value   = ("OK", [])
    client._imap = mock_imap

    with patch("src.gmail_client.config.IMAP_HOST", "imap.gmail.com"), \
         patch("src.gmail_client.config.IMAP_PORT", 993):
        result = client.thread_has_reply_with_attachment("<original@example.com>")

    assert result is False


def test_thread_has_reply_no_matching_messages():
    """IMAP finds no matching messages — should return False."""
    client = _make_client()
    mock_imap = MagicMock()
    mock_imap.search.return_value = ("OK", [b""])
    mock_imap.noop.return_value   = ("OK", [])
    client._imap = mock_imap

    with patch("src.gmail_client.config.IMAP_HOST", "imap.gmail.com"), \
         patch("src.gmail_client.config.IMAP_PORT", 993):
        result = client.thread_has_reply_with_attachment("<original@example.com>")

    assert result is False
