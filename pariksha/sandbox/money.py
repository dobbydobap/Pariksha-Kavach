"""Paise arithmetic and Indian currency formatting.

Razorpay amounts are integer paise: 50000 is Rs 500.00. See D-007, D-008.
This module describes and scores amounts; it never enforces (D-006).
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

PAISE_PER_RUPEE = 100
UNIT_CONFUSION_FACTOR = 100


def rupees_to_paise(rupees: Decimal | int | str) -> int:
    """Convert rupees to integer paise, rounding half-up. Floats are rejected."""
    if isinstance(rupees, float):
        raise TypeError("refusing to convert a float to paise: use Decimal('123.45') or a string")
    value = rupees if isinstance(rupees, Decimal) else Decimal(rupees)
    return int((value * PAISE_PER_RUPEE).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def paise_to_rupees(paise: int) -> Decimal:
    """Convert integer paise to an exact Decimal rupee amount."""
    return (Decimal(paise) / PAISE_PER_RUPEE).quantize(Decimal("0.01"))


def format_inr(paise: int) -> str:
    """Render paise with Indian 2-2-3 digit grouping: 500000000 -> 'Rs 50,00,000.00'."""
    amount = paise_to_rupees(abs(paise))
    whole, _, frac = f"{amount:.2f}".partition(".")

    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join([*groups, tail])

    return f"{'-' if paise < 0 else ''}Rs {whole}.{frac}"


def looks_like_unit_confusion(expected_paise: int, actual_paise: int) -> str | None:
    """Classify an amount mismatch as a clean 100x unit error, or None.

    Separates "wrong number" from "wrong units" for the judges.
    """
    if expected_paise == 0 or actual_paise == expected_paise:
        return None
    if actual_paise * UNIT_CONFUSION_FACTOR == expected_paise:
        return "under_100x"
    if actual_paise == expected_paise * UNIT_CONFUSION_FACTOR:
        return "over_100x"
    return None
