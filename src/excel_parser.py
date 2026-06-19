from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import openpyxl


@dataclass
class Transaction:
    account_name: str
    account_number: str
    allocation_code: str
    posting_date: Optional[datetime]
    amount: float
    merchant_name: str


@dataclass
class Cardholder:
    name: str
    email: str
    account_number: str
    transactions: list[Transaction] = field(default_factory=list)


def parse_transactions(filepath: str) -> list[Cardholder]:
    """
    Parse the 'Main Report' sheet of the CC transaction Excel file.

    Expected columns (1-indexed):
      A  Account Name
      B  Account Number
      C  Allocation Accounting Code
      D  Company Name
      E  Posting Date
      F  Transaction Amount
      G  Transaction Merchant Name
      H  Email  ← added by scripts/add_email_column.py
    """
    wb = openpyxl.load_workbook(filepath)
    ws = wb["Main Report"]

    cardholders: dict[str, Cardholder] = {}

    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row[0]:
            continue

        name     = str(row[0]).strip()
        acct_num = str(row[1]).strip() if row[1] else ""
        email    = str(row[7]).strip() if len(row) > 7 and row[7] else ""

        if name not in cardholders:
            cardholders[name] = Cardholder(
                name=name, email=email, account_number=acct_num
            )

        cardholders[name].transactions.append(
            Transaction(
                account_name=name,
                account_number=acct_num,
                allocation_code=str(row[2]) if row[2] else "",
                posting_date=row[4] if isinstance(row[4], datetime) else None,
                amount=float(row[5]) if row[5] is not None else 0.0,
                merchant_name=str(row[6]).strip() if row[6] else "",
            )
        )

    return list(cardholders.values())
