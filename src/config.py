"""
Centralised configuration — loaded once at import time.
Raises ValueError immediately if a required variable is missing.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise ValueError(
            f"Required environment variable '{key}' is not set.\n"
            "Copy .env.example to .env and fill in the missing values."
        )
    return val


# ── OpenAI ─────────────────────────────────────────────────────────────────
OPENAI_API_KEY   = _require("OPENAI_API_KEY")
OPENAI_MODEL     = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ── Email (SMTP + IMAP) ────────────────────────────────────────────────────
GMAIL_ADDRESS            = _require("GMAIL_ADDRESS")
GMAIL_APP_PASSWORD       = _require("GMAIL_APP_PASSWORD")
SMTP_HOST                = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT                = int(os.getenv("SMTP_PORT", "587"))
IMAP_HOST                = os.getenv("IMAP_HOST", "imap.gmail.com")
IMAP_PORT                = int(os.getenv("IMAP_PORT", "993"))
GMAIL_COMPENSATION_LABEL = os.getenv("GMAIL_COMPENSATION_LABEL", "compensation")

# ── Google Drive ───────────────────────────────────────────────────────────
DRIVE_WATCH_FOLDER_ID       = os.getenv("DRIVE_WATCH_FOLDER_ID", "")
DRIVE_POLL_INTERVAL_SECONDS = int(os.getenv("DRIVE_POLL_INTERVAL_SECONDS", "60"))

# ── Agent ──────────────────────────────────────────────────────────────────
REPLY_POLL_INTERVAL_SECONDS = int(os.getenv("REPLY_POLL_INTERVAL_SECONDS", "30"))
STATE_FILE                  = Path(os.getenv("STATE_FILE", "state/agent_state.json"))
LOG_LEVEL                   = os.getenv("LOG_LEVEL", "INFO")
