"""
Receipt Validator — POC (Mock / Happy Path)

Production implementation would:
  1. Fetch the attachment bytes from the reply email (via IMAP body fetch).
  2. Send the bytes to an LLM (e.g. GPT-4o vision) as a base64 image/document.
  3. Extract merchant name, amount, and date from the receipt.
  4. Compare against the Transaction record:
       - Amount: tolerance ± $0.01
       - Merchant: fuzzy token match
       - Date: ± 3 calendar days
  5. Return approved=True only when all three fields match within tolerance.

POC: Always returns approved=True — happy path only.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.excel_parser import Transaction


@dataclass
class ValidationResult:
    approved: bool
    reason: str


class MockReceiptValidator:
    """Accepts any attachment as a valid receipt. POC happy-path only."""

    def validate(
        self, transaction: Transaction, attachment_filename: str
    ) -> ValidationResult:
        return ValidationResult(
            approved=True,
            reason=(
                f"Mock validation passed — '{attachment_filename}' accepted for "
                f"${transaction.amount:.2f} at {transaction.merchant_name}."
            ),
        )
