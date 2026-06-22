"""
Scripted receipt validator — deterministic by employee name.
No real OCR or document inspection for POC.

Scenarios:
  ERIC WILSON  → always fully approved on reply 1
  TODD BAHR    → always fully approved on reply 1
  KIM WATROBA  → partial fail on reply 1, fully approved on reply 2
  CORY BACH    → partial fail on reply 1, branch on deadline on reply 2
                 (deadline branching handled by coordinator, not here)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    approved: bool
    failed_items: list[str] = field(default_factory=list)
    reason: str = ""


# Scripted partial-fail merchants per employee — returned on first reply only
_PARTIAL_FAIL_ITEMS: dict[str, list[str]] = {
    "KIM WATROBA": [
        "SCREAMING FROG LTD",
        "EPN*EXPERIAN BIZCREDIT",
    ],
    "CORY BACH": [
        "AVIS RENT-A-CAR",
        "AVIS.COM PREPAY",
        "HOLIDAY INN EXPRESS SPGV",
        "TST* GIORDANOS - SCHAUMBU",
        "SHELL OIL 10051243003",
        "FAST PARK CLEVELAND FPR",
    ],
}


class ScriptedReceiptValidator:
    """
    Validates receipts using a deterministic script per employee name.
    reply_count is 1-indexed: 1 = first reply from employee, 2 = second, etc.
    Deadline enforcement (Cory Bach branch 2) is handled by the coordinator.
    """

    def validate(self, employee_name: str, reply_count: int) -> ValidationResult:
        fail_items = _PARTIAL_FAIL_ITEMS.get(employee_name, [])

        # Employees not in fail map → always approve on first reply
        if not fail_items:
            return ValidationResult(
                approved=True,
                reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
            )

        # Scripted partial fail on reply 1
        if reply_count == 1:
            return ValidationResult(
                approved=False,
                failed_items=list(fail_items),
                reason=(
                    f"Partial fail on reply {reply_count}: "
                    f"{len(fail_items)} item(s) could not be parsed."
                ),
            )

        # Reply 2+ → approve (deadline check happens in coordinator before this)
        return ValidationResult(
            approved=True,
            reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
        )


# Backward-compatible alias
MockReceiptValidator = ScriptedReceiptValidator
