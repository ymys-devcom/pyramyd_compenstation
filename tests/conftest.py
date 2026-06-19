import os
import pytest

# ── Set env vars BEFORE any src module is imported (collection time) ───────
# config.py calls _require() at module level, so vars must exist before import.
os.environ.setdefault("OPENAI_API_KEY",      "test-openai-key")
os.environ.setdefault("GMAIL_ADDRESS",       "agent@example.com")
os.environ.setdefault("GMAIL_APP_PASSWORD",  "test-app-password")


@pytest.fixture(autouse=True)
def mock_env(monkeypatch):
    """Keep env vars set throughout each test (overrides any accidental clears)."""
    monkeypatch.setenv("OPENAI_API_KEY",      "test-openai-key")
    monkeypatch.setenv("GMAIL_ADDRESS",       "agent@example.com")
    monkeypatch.setenv("GMAIL_APP_PASSWORD",  "test-app-password")
