"""
CC Expense Coordinator Agent — CLI Entry Point

Usage:
    # Process a local Excel file immediately (demo mode):
    python -m src.agent --local-file data/transactions_sample.xlsx

    # Watch a folder for new Excel uploads (production-like trigger):
    python -m src.agent --watch-drive

    # Print current state and exit:
    python -m src.agent --status
"""
from __future__ import annotations

import argparse
import sys
import time

from loguru import logger

from src import config
from src.excel_parser import parse_transactions
from src.gmail_client import GmailClient
from src.receipt_validator import MockReceiptValidator
from src.coordinator import ExpenseCoordinator


def _build_coordinator() -> ExpenseCoordinator:
    return ExpenseCoordinator(
        gmail=GmailClient(),
        validator=MockReceiptValidator(),
        state_file=str(config.STATE_FILE),
    )


# ---------------------------------------------------------------------------
# Mode 1: local file
# ---------------------------------------------------------------------------

def run_local(filepath: str) -> None:
    logger.info(f"LOCAL mode — file: {filepath}")
    cardholders = parse_transactions(filepath)
    names = ", ".join(ch.name for ch in cardholders)
    logger.info(f"Parsed {len(cardholders)} cardholder(s): {names}")

    coord = _build_coordinator()
    coord.process_new_statement(cardholders)
    coord.print_status()

    logger.info(
        f"Polling for replies every {config.REPLY_POLL_INTERVAL_SECONDS}s. "
        "Reply to any outreach email with a file attached. Ctrl+C to stop."
    )
    try:
        while not coord.all_resolved():
            coord.check_for_replies()
            if coord.all_resolved():
                break
            time.sleep(config.REPLY_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Interrupted.")

    coord.print_status()
    if coord.all_resolved():
        logger.success("All cardholders resolved — agent complete.")
    else:
        logger.info("Agent stopped. Re-run to resume (state is persisted).")


# ---------------------------------------------------------------------------
# Mode 2: watch folder
# ---------------------------------------------------------------------------

def run_watch_drive() -> None:
    folder = config.DRIVE_WATCH_FOLDER_ID
    if not folder:
        logger.error(
            "DRIVE_WATCH_FOLDER_ID is not set in .env.\n"
            "Set it to a local folder path, e.g.:\n"
            "  DRIVE_WATCH_FOLDER_ID=C:\\Users\\you\\Desktop\\cc-uploads"
        )
        sys.exit(1)

    from src.drive_client import DriveClient
    drive  = DriveClient()
    coord  = _build_coordinator()
    known: set[str] = set()

    logger.info(
        f"Watching folder '{folder}' every {config.DRIVE_POLL_INTERVAL_SECONDS}s. "
        "Drop a .xlsx file there to trigger the agent. Ctrl+C to stop."
    )
    try:
        while True:
            new_file = drive.get_latest_xlsx(folder, known)
            if new_file:
                logger.info(f"New file: {new_file['name']}")
                dest = f"state/downloaded_{new_file['name']}"
                drive.download_file(new_file["id"], dest)
                known.add(new_file["id"])
                cardholders = parse_transactions(dest)
                coord.process_new_statement(cardholders)
                coord.print_status()

            coord.check_for_replies()
            time.sleep(config.DRIVE_POLL_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        logger.info("Interrupted.")
        coord.print_status()


# ---------------------------------------------------------------------------
# Mode 3: status only
# ---------------------------------------------------------------------------

def show_status() -> None:
    coord = _build_coordinator()
    if not coord._state:
        print("No state file found — agent has not run yet.")
    else:
        coord.print_status()


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------

def main() -> None:
    logger.remove()
    logger.add(
        sys.stderr, level=config.LOG_LEVEL, colorize=True,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
    )

    parser = argparse.ArgumentParser(description="CC Expense Coordinator Agent (POC)")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--local-file", metavar="PATH",
                       help="Process a local .xlsx file immediately")
    group.add_argument("--watch-drive", action="store_true",
                       help="Watch a folder for new .xlsx uploads")
    group.add_argument("--status", action="store_true",
                       help="Print current state and exit")
    args = parser.parse_args()

    if args.local_file:
        run_local(args.local_file)
    elif args.watch_drive:
        run_watch_drive()
    else:
        show_status()


if __name__ == "__main__":
    main()
