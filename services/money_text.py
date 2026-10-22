"""Euro amounts in the words the guard's dialogs and refusals use.

Every figure is two decimals, rounded in the direction that keeps the words
true to the decision (spec Design, "Money format"): a maximum rounds up, an
amount left rounds down, so "up to €0.44 and €0.43 left" is always a refusal
and never a rounding accident. A paid amount under a cent reads "under €0.01",
never "€0.00".

Decimal via `str`, as in services/validator.py: `Decimal(0.43)` keeps the
binary error and would round 0.43 up to 0.44.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP, Decimal

_CENT = Decimal("0.01")


def _decimal(value) -> Decimal:
    # Six places first: costs are stored to the micro-euro, and a float sum
    # such as 0.1 + 0.2 must not ceil to 0.31.
    return Decimal(str(round(float(value or 0.0), 6)))


def up_to(eur) -> str:
    """A maximum: "€0.44" for €0.4330."""
    return f"€{_decimal(eur).quantize(_CENT, rounding=ROUND_CEILING)}"


def left(eur) -> str:
    """An amount still available: rounded down, never below €0.00."""
    amount = max(Decimal(0), _decimal(eur))
    return f"€{amount.quantize(_CENT, rounding=ROUND_FLOOR)}"


def paid(eur) -> str:
    """An amount recorded or spent: "under €0.01" rather than "€0.00"."""
    amount = _decimal(eur)
    if Decimal(0) < amount < _CENT:
        return "under €0.01"
    return f"€{amount.quantize(_CENT, rounding=ROUND_HALF_UP)}"
