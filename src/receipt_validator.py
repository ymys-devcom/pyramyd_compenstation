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
    reply_count is 1-indexed: 1 = first reply, 2 = second, etc.

    Cory Bach flow (3-reply path):
      reply 1 → partial fail (no deadline yet)
      reply 2 → partial fail again  ← coordinator sets 5-min deadline here
      reply 3 → approved            ← coordinator checks deadline before calling this

    Kim Watroba flow (2-reply path):
      reply 1 → partial fail
      reply 2 → approved

    Eric Wilson / Todd Bahr (1-reply path):
      reply 1 → approved
    """

    def validate(self, employee_name: str, reply_count: int) -> ValidationResult:
        fail_items = _PARTIAL_FAIL_ITEMS.get(employee_name, [])

        if not fail_items:
            return ValidationResult(
                approved=True,
                reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
            )

        # Kim: fail on reply 1, approve on reply 2
        if employee_name == "KIM WATROBA":
            if reply_count == 1:
                return ValidationResult(
                    approved=False,
                    failed_items=list(fail_items),
                    reason=f"Partial fail on reply {reply_count}.",
                )
            return ValidationResult(
                approved=True,
                reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
            )

        # Cory: fail on reply 1 AND reply 2, approve on reply 3+
        # (deadline check for reply 3 is handled by coordinator before calling here)
        if employee_name == "CORY BACH":
            if reply_count <= 2:
                return ValidationResult(
                    approved=False,
                    failed_items=list(fail_items),
                    reason=f"Partial fail on reply {reply_count}.",
                )
            return ValidationResult(
                approved=True,
                reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
            )

        # Default: approve on first reply
        return ValidationResult(
            approved=True,
            reason=f"All receipts validated for {employee_name} (reply {reply_count}).",
        )


# Backward-compatible alias
MockReceiptValidator = ScriptedReceiptValidator
