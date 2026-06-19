# CC Expense Coordinator Agent
## Full User & Operations Guide

**Version:** 1.0 — POC  
**Repo:** https://github.com/ymys-devcom/pyramyd_compenstation  
**Maintained by:** DevCom Consulting LLC

---

## Table of Contents

1. [What This Agent Does](#1-what-this-agent-does)
2. [How It Works — Step by Step](#2-how-it-works--step-by-step)
3. [For Employees — What to Expect](#3-for-employees--what-to-expect)
4. [First-Time Setup (Admin)](#4-first-time-setup-admin)
5. [How to Trigger the Agent — Uploading the Monthly Excel](#5-how-to-trigger-the-agent--uploading-the-monthly-excel)
6. [Running the Agent Manually](#6-running-the-agent-manually)
7. [Making the Agent Always Available (Auto-Start on Windows)](#7-making-the-agent-always-available-auto-start-on-windows)
8. [Checking Agent Status](#8-checking-agent-status)
9. [Resetting the Agent for a New Month](#9-resetting-the-agent-for-a-new-month)
10. [Troubleshooting](#10-troubleshooting)
11. [Technical Reference](#11-technical-reference)

---

## 1. What This Agent Does

Every month your company generates a credit card transaction Excel file listing employee expenses that need to be reimbursed (subscriptions, travel, meals, etc.). Normally, a manager manually emails each employee one by one asking them to send proof of purchase.

**This agent automates that entire process:**

- Reads the monthly Excel file automatically
- Sends a personalised email to each employee listing their specific transactions
- Waits for the employee to reply with their receipt or confirmation document attached
- Automatically sends an approval/success email once a document is received
- All emails are tagged **`compensation`** in Gmail for easy tracking

```
┌─────────────────────────────────────────────────────────────────┐
│                     MONTHLY FLOW                                │
│                                                                 │
│  Finance uploads        Agent reads file        Agent emails   │
│  Excel to Drive   ───►  & finds 3 employees ──► each employee  │
│                                                                 │
│  Employee replies       Agent detects           Agent sends    │
│  with receipt     ───►  the attachment    ────► approval email │
│                                                                 │
│              All emails tagged "compensation" in Gmail          │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. How It Works — Step by Step

### Step 1 — Trigger
The process starts in one of two ways:
- **Manual:** Someone runs the agent with a specific Excel file path
- **Automatic (Watch mode):** The agent monitors a Google Drive–synced folder; when a new `.xlsx` file is dropped there, it starts automatically

### Step 2 — Parse the Excel File
The agent reads the **Main Report** sheet of the file. It looks for these columns:

| Column | What it reads |
|--------|--------------|
| A — Account Name | Employee's full name |
| E — Posting Date | Date of the transaction |
| F — Transaction Amount | Dollar amount |
| G — Transaction Merchant Name | Where they spent |
| H — Email | Employee's email address *(must be filled in by Finance)* |

It groups all transactions by employee (cardholder).

### Step 3 — Send Outreach Emails
For each unique employee, the agent:
1. Uses **OpenAI GPT-4o Mini** to write a friendly, professional email listing that employee's specific transactions
2. Sends it from `support@ai.devcom.com` via Gmail
3. Applies the **`compensation`** label to the email in Gmail

Example email sent to employee:

> *Subject: Action Required: Receipt Submission for Credit Card Transactions — CORY BACH*
>
> Hi Cory,
>
> I hope you're doing well! I'm reaching out regarding some recent credit card transactions that require receipt or confirmation documents for our monthly expense reconciliation:
>
> • 2025-05-28 | $37.64 | AMERICAN AIR  
> • 2025-05-29 | $893.49 | AVIS.COM PREPAY  
> • 2025-06-19 | $33.67 | DICKEY'S BBQ
>
> Please reply to this email with the relevant receipt(s) or confirmation document(s) attached. This email is tagged for compensation tracking.
>
> Thank you for your prompt attention!
>
> The Finance Team

### Step 4 — Monitor for Replies
The agent polls Gmail (IMAP) every **30 seconds**, looking for any reply to its outreach emails that contains a file attachment.

### Step 5 — Approve & Confirm
When an employee replies with any attached file:
1. The agent validates the receipt *(mock approval in POC — always approves)*
2. GPT-4o Mini drafts a warm approval email
3. The approval is sent as a reply in the **same email thread**
4. The thread is re-tagged `compensation`
5. The employee's status is saved as **`approved`**

Example approval email sent back:

> *Subject: Expense Approved — Receipt Received for CORY BACH*
>
> Hi Cory,
>
> Great news! We've received your receipt and your expense has been approved. Your compensation request is being processed.
>
> Thank you for your quick response!
>
> The Finance Team

### Step 6 — Persist State
Everything is saved to `state/agent_state.json`. If the agent is stopped and restarted, it resumes exactly where it left off — it won't re-send emails to employees it already contacted.

---

## 3. For Employees — What to Expect

**You will receive an email from `support@ai.devcom.com`** with the subject:
> *"Action Required: Receipt Submission for Credit Card Transactions — [YOUR NAME]"*

The email will list your recent company credit card transactions.

### What you need to do:

1. **Reply to the email** (do not create a new email — use the Reply button)
2. **Attach your receipt or confirmation document** — this can be:
   - A PDF of the receipt
   - A photo of the receipt (JPG, PNG)
   - A bank statement screenshot
   - Any document that confirms the purchase
3. **Send your reply**

Within **30 seconds** you will receive a confirmation email in the same thread confirming your expense has been approved.

> ⚠️ **Important:** You must attach a file to your reply. A text-only reply will not trigger the approval. The attached file can be anything — even a screenshot works.

---

## 4. First-Time Setup (Admin)

### Prerequisites
- Windows 10/11 machine that will run the agent
- Python 3.11 installed
- Git installed
- OpenAI API key (from https://platform.openai.com)
- Access to `support@ai.devcom.com` Google Workspace account

### 4.1 Clone the Repository

Open **Git Bash** and run:

```bash
mkdir -p /c/Users/YOUR_USERNAME/projects
cd /c/Users/YOUR_USERNAME/projects
git clone https://github.com/ymys-devcom/pyramyd_compenstation.git
cd pyramyd_compenstation
```

### 4.2 Create Virtual Environment & Install Dependencies

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
```

Verify installation:
```bash
python -c "import openai, openpyxl, imapclient; print('All dependencies OK')"
```

### 4.3 Generate a Gmail App Password

The agent uses an **App Password** to access Gmail — no Google Cloud Console setup needed.

1. Sign in to https://myaccount.google.com with `support@ai.devcom.com`
2. Go to **Security** → **2-Step Verification** → enable it if not already on
3. Go to **Security** → search for **"App Passwords"** in the search box
4. Click **Create a new App Password**, name it `cc-agent`, click **Create**
5. Copy the **16-character password** shown (e.g. `abcd efgh ijkl mnop`)

> **Google Workspace note:** If "App Passwords" is not visible, a Workspace admin must enable it under:  
> Admin Console → Security → Less Secure Apps → *Allow users to manage their access*

### 4.4 Configure the Environment File

```bash
cp .env.example .env
```

Open `.env` in any text editor and fill in:

```env
OPENAI_API_KEY=sk-proj-...your-real-key-here...
GMAIL_ADDRESS=support@ai.devcom.com
GMAIL_APP_PASSWORD=abcdefghijklmnop
```

Everything else can stay at its default value.

### 4.5 Prepare the Excel Template

The agent expects an **Email column (column H)** in the Excel file. Run the helper script once to add it to the sample file:

```bash
python scripts/add_email_column.py
```

Then open `data/transactions_sample.xlsx`, go to the **Main Report** sheet, and fill in real employee email addresses in column H.

### 4.6 Verify Everything Works

```bash
source .venv/Scripts/activate
python -m src.agent --local-file data/transactions_sample.xlsx
```

You should see:
```
INFO  | LOCAL mode — file: data/transactions_sample.xlsx
INFO  | Parsed 3 cardholder(s): CORY BACH, TODD BAHR, ARIEL BENEWIAT
INFO  | Sent → employee@company.com | subject='Action Required...'
SUCCESS | Outreach sent → CORY BACH <employee@company.com>
...
INFO  | Polling for replies every 30s. Ctrl+C to stop.
```

Press **Ctrl+C** to stop after confirming emails were sent.

---

## 5. How to Trigger the Agent — Uploading the Monthly Excel

### Option A — Google Drive (Recommended for Production)

This is the cleanest workflow for Finance: just upload the Excel to a shared Drive folder and the agent processes it automatically.

#### Setup (one-time)

1. **Install Google Drive for Desktop** on the machine running the agent:  
   https://www.google.com/drive/download/

2. Sign in and enable **"Mirror files"** (not stream) so files are available locally.

3. Create a shared folder in Google Drive called `CC Monthly Statements` (or any name). Note its local path — Google Drive for Desktop maps Drive folders to:
   ```
   C:\Users\YOUR_USERNAME\Google Drive\My Drive\CC Monthly Statements\
   ```

4. Set this path in `.env`:
   ```env
   DRIVE_WATCH_FOLDER_ID=C:\Users\YOUR_USERNAME\Google Drive\My Drive\CC Monthly Statements
   ```

5. Run the agent in watch mode:
   ```bash
   source .venv/Scripts/activate
   python -m src.agent --watch-drive
   ```

#### Monthly Workflow (Finance Team)

Every month, follow these steps:

**Step 1 — Prepare the Excel file**

Open the monthly CC transaction Excel export. Make sure column H (`Email`) is filled with each cardholder's email address. Save the file.

> If the Email column is missing, run:
> ```bash
> python scripts/add_email_column.py
> ```
> Then fill in the emails in `data/transactions_sample.xlsx`.

**Step 2 — Upload to Google Drive**

Drag and drop (or upload) the `.xlsx` file into the shared `CC Monthly Statements` folder in Google Drive.

```
Google Drive → CC Monthly Statements → Drop file here
```

**Step 3 — Agent picks it up automatically**

Within **60 seconds** (the Drive poll interval), the agent:
- Detects the new file
- Downloads it
- Parses all cardholders
- Sends outreach emails to everyone

You will see in the agent log:
```
INFO    | New file: CCCoordinator_transactionFile_June2026.xlsx
SUCCESS | Outreach sent → CORY BACH <cory.bach@company.com>
SUCCESS | Outreach sent → TODD BAHR <todd.bahr@company.com>
SUCCESS | Outreach sent → ARIEL BENEWIAT <ariel.benewiat@company.com>
```

**Step 4 — Agent handles everything else**

The agent keeps running and monitors for employee replies. No further action needed from Finance.

---

### Option B — Manual Run (Simpler, No Drive Setup)

If you don't want to set up Google Drive for Desktop, you can trigger the agent manually each month.

**Step 1 — Place the Excel file** in the project folder:
```
C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation\data\
```

**Step 2 — Run the agent:**
```bash
cd C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation
source .venv/Scripts/activate
python -m src.agent --local-file data/your-monthly-file.xlsx
```

The agent will send all emails and then stay running to monitor replies. Keep the window open.

---

## 6. Running the Agent Manually

Open **Git Bash** and run:

```bash
cd C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation
source .venv/Scripts/activate

# Process a specific file right now:
python -m src.agent --local-file data/transactions_sample.xlsx

# Watch the Google Drive folder for new uploads:
python -m src.agent --watch-drive

# Just check the current status (no emails sent):
python -m src.agent --status
```

---

## 7. Making the Agent Always Available (Auto-Start on Windows)

For the agent to run continuously (survive reboots, start automatically), set it up as a **Windows Scheduled Task**. No extra software required.

### Method A — Windows Task Scheduler (Recommended)

#### Step 1 — Create a launcher script

Create the file `C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation\run_agent.bat`:

```bat
@echo off
cd /d C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation
call .venv\Scripts\activate.bat
python -m src.agent --watch-drive >> logs\agent.log 2>&1
```

Also create the logs folder:
```bash
mkdir -p /c/Users/YOUR_USERNAME/projects/pyramyd_compenstation/logs
```

#### Step 2 — Open Task Scheduler

Press `Win + R`, type `taskschd.msc`, press Enter.

#### Step 3 — Create a new task

1. Click **"Create Task"** (right panel)
2. **General tab:**
   - Name: `CC Expense Coordinator Agent`
   - Check **"Run whether user is logged on or not"**
   - Check **"Run with highest privileges"**
3. **Triggers tab** → New:
   - Begin the task: **"At startup"**
   - Delay task for: `1 minute` (gives the machine time to connect to network)
   - Check **"Enabled"**
4. **Actions tab** → New:
   - Action: **"Start a program"**
   - Program/script: `C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation\run_agent.bat`
5. **Settings tab:**
   - Check **"If the task is already running, do not start a new instance"**
   - Uncheck **"Stop the task if it runs longer than..."**
6. Click **OK**, enter your Windows password when prompted.

#### Step 4 — Test it

Right-click the task → **"Run"**. Open Task Manager → Details tab → confirm `python.exe` is running.

Check the log file to confirm it started:
```bash
cat /c/Users/YOUR_USERNAME/projects/pyramyd_compenstation/logs/agent.log
```

---

### Method B — NSSM (Run as a True Windows Service)

For more robust production use, install NSSM (Non-Sucking Service Manager):

1. Download NSSM from https://nssm.cc/download → extract to `C:\tools\nssm\`

2. Open **Command Prompt as Administrator** and run:
```cmd
C:\tools\nssm\win64\nssm.exe install CCExpenseAgent
```

3. In the dialog that appears:
   - **Path:** `C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation\.venv\Scripts\python.exe`
   - **Startup directory:** `C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation`
   - **Arguments:** `-m src.agent --watch-drive`

4. Go to the **I/O** tab:
   - Output (stdout): `C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation\logs\agent.log`
   - Error (stderr): same path

5. Click **Install service**, then:
```cmd
nssm start CCExpenseAgent
```

The agent now runs as a Windows service — starts automatically on boot, restarts on crash.

To check status:
```cmd
nssm status CCExpenseAgent
```

To stop:
```cmd
nssm stop CCExpenseAgent
```

---

## 8. Checking Agent Status

### Via CLI

```bash
cd C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation
source .venv/Scripts/activate
python -m src.agent --status
```

Output example:
```
Cardholder                Status           Sent at
----------------------------------------------------------------------
CORY BACH                 approved         2026-06-19T09:57:20
TODD BAHR                 outreach_sent    2026-06-19T09:57:25
ARIEL BENEWIAT            outreach_sent    2026-06-19T09:57:28
```

| Status | Meaning |
|--------|---------|
| `pending` | Not yet contacted |
| `outreach_sent` | Email sent, waiting for reply with attachment |
| `approved` | Receipt received, success email sent |

### Via Gmail

All agent emails — both outreach and approval — are tagged with the **`compensation`** label in Gmail.

To find them:
1. Open Gmail as `support@ai.devcom.com`
2. In the left sidebar, find **"compensation"** under Labels
3. All threads are listed there with their status visible from the subject line

### Via the State File

The raw state is stored in `state/agent_state.json`. You can open it in any text editor or VS Code to see exactly what the agent knows about each cardholder.

---

## 9. Resetting the Agent for a New Month

At the start of each new month, reset the agent's state so it will process a fresh Excel file:

```bash
cd C:\Users\YOUR_USERNAME\projects\pyramyd_compenstation

# Delete the state file (agent will start fresh)
rm state/agent_state.json
```

Then either:
- **Drop the new Excel file** into the watched Google Drive folder (auto-trigger), or
- **Run manually:** `python -m src.agent --local-file data/new-month-file.xlsx`

> **Important:** Always reset state before processing a new month's file. Without resetting, the agent will skip employees it already contacted last month.

---

## 10. Troubleshooting

### "SMTP Authentication Error" or "App Password rejected"

**Cause:** The Gmail App Password is wrong or expired.

**Fix:**
1. Go to https://myaccount.google.com → Security → App Passwords
2. Delete the old `cc-agent` password
3. Create a new one and update `.env`:
   ```
   GMAIL_APP_PASSWORD=new-16-char-password
   ```

---

### "Required environment variable 'OPENAI_API_KEY' is not set"

**Cause:** The `.env` file is missing or the key is empty.

**Fix:**
```bash
# Verify the file exists and has the key
cat .env | grep OPENAI_API_KEY
```
If it's empty or missing, add your key. Get a key from https://platform.openai.com/api-keys.

---

### "App Passwords not visible in Google account"

**Cause:** Google Workspace admin has not enabled App Passwords for users.

**Fix (Admin):** Go to Google Admin Console → Security → Less Secure Apps → enable per-user control. Then the user can generate an App Password from their own account settings.

---

### Agent sent emails but employees never got them

**Check 1:** Ask employees to check their Spam folder — the first email from a new sender may be filtered.

**Check 2:** Verify the email addresses in column H of the Excel file are correct.

**Check 3:** Verify SMTP worked by checking the agent log for `Sent →` lines.

---

### "Agent detects no replies" even after employee replied with attachment

**Possible cause 1:** Employee replied but didn't attach a file. The agent only triggers on replies with attachments — a text-only reply is ignored.

**Possible cause 2:** IMAP is slow to index new emails. Wait up to 60 seconds and the next poll cycle will catch it.

**Possible cause 3:** The employee replied from a different email address than the one in the Excel file. The agent matches by `In-Reply-To` header (email thread), not by sender address — so this should still work as long as they replied to the original thread.

---

### Agent stopped mid-month — will it re-send emails?

**No.** The agent is idempotent. When restarted, it reads `state/agent_state.json` and skips anyone with status `outreach_sent` or `approved`. It will only send new emails to anyone still in `pending` status.

Simply restart the agent and it will resume monitoring existing threads.

---

### "DRIVE_WATCH_FOLDER_ID is not set" error in --watch-drive mode

**Fix:** Make sure `.env` has the folder path set:
```env
DRIVE_WATCH_FOLDER_ID=C:\Users\YOUR_USERNAME\Google Drive\My Drive\CC Monthly Statements
```
Use **backslashes** for Windows paths in the `.env` file.

---

## 11. Technical Reference

### Project Structure

```
pyramyd_compenstation/
├── .env                        ← Your secrets (never committed to git)
├── .env.example                ← Template showing all available settings
├── requirements.txt            ← Python dependencies
├── data/
│   └── transactions_sample.xlsx  ← Sample file with Email column
├── scripts/
│   └── add_email_column.py     ← One-time helper to add Email column to xlsx
├── src/
│   ├── config.py               ← Loads .env, validates required vars
│   ├── excel_parser.py         ← Reads xlsx → Cardholder/Transaction objects
│   ├── email_templates.py      ← OpenAI GPT-4o Mini email drafting
│   ├── gmail_client.py         ← SMTP send + IMAP reply detection
│   ├── drive_client.py         ← Watches local folder for new xlsx files
│   ├── receipt_validator.py    ← Mock validator (POC — always approves)
│   ├── coordinator.py          ← Orchestrates the full workflow + state
│   └── agent.py                ← CLI entry point
├── state/
│   └── agent_state.json        ← Live agent state (auto-created at runtime)
└── tests/                      ← 23 unit tests
```

### All Configuration Options (`.env`)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | ✅ Yes | — | OpenAI API key |
| `OPENAI_MODEL` | No | `gpt-4o-mini` | Model used for email drafting |
| `GMAIL_ADDRESS` | ✅ Yes | — | Gmail address the agent sends from |
| `GMAIL_APP_PASSWORD` | ✅ Yes | — | 16-char Gmail App Password |
| `SMTP_HOST` | No | `smtp.gmail.com` | SMTP server |
| `SMTP_PORT` | No | `587` | SMTP port |
| `IMAP_HOST` | No | `imap.gmail.com` | IMAP server |
| `IMAP_PORT` | No | `993` | IMAP port |
| `GMAIL_COMPENSATION_LABEL` | No | `compensation` | Gmail label name |
| `DRIVE_WATCH_FOLDER_ID` | No | — | Local folder path for watch mode |
| `DRIVE_POLL_INTERVAL_SECONDS` | No | `60` | How often to check for new files |
| `REPLY_POLL_INTERVAL_SECONDS` | No | `30` | How often to check for email replies |
| `STATE_FILE` | No | `state/agent_state.json` | Where to save agent state |
| `LOG_LEVEL` | No | `INFO` | Log verbosity |

### Excel File Format

The agent reads the **`Main Report`** sheet. Required columns:

| Column | Header | Required |
|--------|--------|----------|
| A | Account Name | ✅ Employee full name |
| E | Posting Date | ✅ Transaction date |
| F | Transaction Amount | ✅ Dollar amount |
| G | Transaction Merchant Name | ✅ Vendor name |
| H | Email | ✅ Employee email *(must be added manually)* |

Columns B, C, D are read but not used for email sending.

### CLI Commands

```bash
# Process a file immediately
python -m src.agent --local-file path/to/file.xlsx

# Watch a folder for new uploads (runs indefinitely)
python -m src.agent --watch-drive

# Show current status table and exit
python -m src.agent --status
```

### State File Schema

`state/agent_state.json` stores one entry per cardholder:

```json
{
  "CORY BACH": {
    "name": "CORY BACH",
    "email": "cory.bach@company.com",
    "status": "approved",
    "message_id": "<abc123@ai.devcom.com>",
    "sent_at": "2026-06-19T09:57:20",
    "approved_at": "2026-06-19T10:15:44",
    "transactions": [
      {"merchant_name": "AMERICAN AIR", "amount": 37.64},
      {"merchant_name": "AVIS.COM PREPAY", "amount": 893.49}
    ]
  }
}
```

### Running Tests

```bash
source .venv/Scripts/activate
python -m pytest tests/ -v
```

All 23 tests are fully mocked and require no API keys or live connections.

---

*Document prepared by DevCom Consulting LLC · June 2026*
