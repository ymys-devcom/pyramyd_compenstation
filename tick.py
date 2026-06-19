"""
CC Expense Coordinator — single tick script.

Designed to be called by Hermes cron every minute.
Each run does exactly two things:
  1. Check the watch folder for a new .xlsx file — if found, parse it and
     send outreach emails to all cardholders not yet contacted.
  2. Check all open Gmail threads for replies with attachments — if found,
     send the success/approval email.

State is persisted in state/agent_state.json between ticks, so nothing is
ever sent twice and the agent resumes correctly after a restart or gap.

Usage (manual test):
    python tick.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# ── ensure project root is on the path when called from outside the dir ──
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)   # make relative paths (.env, state/, data/) work

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

from loguru import logger
from src import config
from src.excel_parser import parse_transactions
from src.gmail_client import GmailClient
from src.receipt_validator import MockReceiptValidator
from src.coordinator import ExpenseCoordinator
from src.drive_client import DriveClient

logger.remove()
logger.add(sys.stderr, level=config.LOG_LEVEL, colorize=False,
           format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {message}")

# ── persistent file that tracks which Drive files we've already processed ─
SEEN_FILE = ROOT / "state" / "seen_drive_files.json"

def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        return set(json.loads(SEEN_FILE.read_text()))
    return set()

def save_seen(seen: set[str]) -> None:
    SEEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    SEEN_FILE.write_text(json.dumps(list(seen)))


def main() -> None:
    logger.info(f"── tick start {datetime.utcnow().isoformat()} ──")

    gmail     = GmailClient()
    validator = MockReceiptValidator()
    coord     = ExpenseCoordinator(
        gmail=gmail, validator=validator, state_file=str(config.STATE_FILE)
    )

    # ── 1. Check watch folder for new Excel file ───────────────────────────
    watch_folder = config.DRIVE_WATCH_FOLDER_ID
    if watch_folder:
        drive    = DriveClient()
        seen     = load_seen()
        new_file = drive.get_latest_xlsx(watch_folder, seen)
        if new_file:
            logger.info(f"New file detected: {new_file['name']}")
            dest = str(ROOT / "state" / f"downloaded_{new_file['name']}")
            drive.download_file(new_file["id"], dest)
            seen.add(new_file["id"])
            save_seen(seen)

            # Reset state so a new monthly file always triggers fresh outreach
            state_path = ROOT / config.STATE_FILE
            if state_path.exists():
                state_path.unlink()
                logger.info("State reset for new monthly file.")
            coord = ExpenseCoordinator(
                gmail=gmail, validator=validator, state_file=str(config.STATE_FILE)
            )

            cardholders = parse_transactions(dest)
            logger.info(
                f"Parsed {len(cardholders)} cardholder(s): "
                f"{', '.join(ch.name for ch in cardholders)}"
            )
            coord.process_new_statement(cardholders)
            coord.print_status()
        else:
            logger.info("No new file — nothing to process.")
    else:
        logger.info("DRIVE_WATCH_FOLDER_ID not set — skipping file check.")

    # ── 2. Poll for replies ────────────────────────────────────────────────
    if coord._state:
        pending = [n for n, e in coord._state.items()
                   if e.get("status") == "outreach_sent"]
        if pending:
            logger.info(f"Checking replies for: {', '.join(pending)}")
            coord.check_for_replies()
            coord.print_status()
        else:
            logger.info("No pending cardholders — nothing to poll.")
    else:
        logger.info("State is empty — no outreach sent yet.")

    logger.info("── tick end ──")


if __name__ == "__main__":
    main()
