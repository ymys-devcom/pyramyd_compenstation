"""
Merchant whitelist for auto-approved recurring expenses.
Matching: case-insensitive substring.
  Entry "AMAZON" matches "AMAZON MKTPL*NQ10Q3GX2", "AMAZON MKTPL*NO0TZ17C0", etc.

To add more merchants, extend RECURRING_WHITELIST.
"""
from __future__ import annotations

RECURRING_WHITELIST: list[str] = [
    "AMAZON",
]


def is_whitelisted(merchant_name: str) -> bool:
    """Return True if merchant_name contains any whitelist entry (case-insensitive)."""
    name_lower = merchant_name.lower()
    return any(entry.lower() in name_lower for entry in RECURRING_WHITELIST)
