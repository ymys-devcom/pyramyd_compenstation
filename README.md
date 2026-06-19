# CC Expense Coordinator Agent — POC

Automates monthly credit card expense receipt collection via email.
Built on the same patterns as the AP Invoice Agent — no Google Cloud Console or OAuth required.

## What it does

1. Reads the monthly CC transaction Excel file (9 transactions, 3 cardholders)
2. Uses OpenAI `gpt-4o-mini` to draft a personalised outreach email per cardholder listing their transactions and requesting a receipt
3. Sends each email from `support@ai.devcom.com` via SMTP — tagged `compensation`
4. Polls Gmail every 30 s for replies that contain any file attachment
5. On receipt detected: mock-validates (always passes in POC), drafts a success/approval email, sends it as a reply in the same thread — also tagged `compensation`

## Architecture

```
Excel file ──► parse cardholders ──► SMTP outreach (tagged "compensation")
                                              │
                                    poll IMAP every 30s
                                              │
                                    detect attachment reply
                                              │
                                    mock validate ──► success email (same thread)
                                              │
                                    state/agent_state.json updated
```

## Pre-requisites

- Python 3.11
- OpenAI API key
- Gmail App Password for `support@ai.devcom.com`

## Setup

### Step 1 — Clone and install

```bash
git clone https://github.com/ymys-devcom/pyramyd_compenstation.git
cd pyramyd_compenstation
python -m venv .venv
source .venv/Scripts/activate   # Windows Git Bash
pip install -r requirements.txt
```

### Step 2 — Generate a Gmail App Password (one-time, ~60 seconds)

App Passwords are 16-character passwords that let apps access Gmail via SMTP/IMAP
without OAuth. They require 2-Step Verification to be enabled on the account.

1. Sign in to the account at [myaccount.google.com](https://myaccount.google.com)
2. Go to **Security** → **2-Step Verification** → enable it if not already on
3. Go to **Security** → **App Passwords** (you may need to search for it)
4. Click **Create**, choose a name (e.g. "cc-agent"), click **Create**
5. Copy the 16-character password shown (e.g. `abcd efgh ijkl mnop`)

> **Google Workspace accounts:** If you don't see "App Passwords", a Workspace admin
> may need to enable it under Admin console → Security → Less secure apps, or the
> account may need to have 2-Step Verification enforced per user.

### Step 3 — Configure environment

```bash
cp .env.example .env
```

Edit `.env`:
```
OPENAI_API_KEY=sk-...your-key...
GMAIL_ADDRESS=support@ai.devcom.com
GMAIL_APP_PASSWORD=abcdefghijklmnop   # 16-char App Password, no spaces
```

### Step 4 — Add your email to the Excel file

Open `data/transactions_sample.xlsx` → `Main Report` sheet → column H (`Email`).
Replace `cory.bach@placeholder.com` with **your real email address** so you receive
and can reply to the outreach email during the demo.

## Running the Agent

**Demo mode (local file, immediate):**
```bash
python -m src.agent --local-file data/transactions_sample.xlsx
```

**Watch folder for new uploads (production-like trigger):**
```bash
# Set DRIVE_WATCH_FOLDER_ID to a local folder path in .env, e.g.:
# DRIVE_WATCH_FOLDER_ID=C:\Users\you\Desktop\cc-uploads
python -m src.agent --watch-drive
```

**Check state without running:**
```bash
python -m src.agent --status
```

**Reset and start fresh:**
```bash
rm state/agent_state.json
```

## Happy-Path Demo Walkthrough

1. Run `python -m src.agent --local-file data/transactions_sample.xlsx`
2. Three outreach emails arrive from `support@ai.devcom.com`
3. Each email is tagged `compensation` in Gmail
4. Reply to the email addressed to you with **any file attached** (PDF, image, anything)
5. Within 30 s the agent detects your reply
6. A success/approval email arrives in the same thread, also tagged `compensation`
7. Run `python -m src.agent --status` to see the updated state

## Tests

All 23 tests are fully mocked — no API key or live email connection required:

```bash
python -m pytest tests/ -v
```

## File Structure

```
src/
  config.py           Environment variable loading + validation
  excel_parser.py     Parse xlsx → Cardholder + Transaction dataclasses
  email_templates.py  OpenAI email drafting (outreach + success)
  gmail_client.py     SMTP send + IMAP reply detection (App Password auth)
  drive_client.py     Local folder watcher (drop-in for real Drive API)
  receipt_validator.py  Mock validator (always approves — POC happy path)
  coordinator.py      Orchestration loop + JSON state machine
  agent.py            CLI entry point (--local-file | --watch-drive | --status)

scripts/
  add_email_column.py   One-off helper to add Email column to the Excel file

tests/
  conftest.py           Shared env var fixtures
  test_excel_parser.py
  test_email_templates.py
  test_gmail_client.py
  test_coordinator.py
```

## Production Path

| Component | POC | Production |
|-----------|-----|------------|
| Auth | SMTP/IMAP App Password | Same (or OAuth service account) |
| Email AI | OpenAI gpt-4o-mini | Same |
| Receipt validation | Mock (always approves) | GPT-4o Vision OCR + amount/merchant/date match |
| Drive trigger | Local folder watch | Google Drive API polling (swap `DriveClient`) |
| State | Local JSON file | PostgreSQL (same schema) |
| Escalation | Not implemented | Day-N reminder, Day-M manager escalation |
