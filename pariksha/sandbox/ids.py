"""Deterministic Razorpay-shaped entity IDs, e.g. pay_29QQoUBi66xm2f. See D-011."""

from __future__ import annotations

import random
import string

ID_ALPHABET = string.ascii_letters + string.digits
ID_BODY_LENGTH = 14

PREFIXES = {
    "order": "order",
    "payment": "pay",
    "refund": "rfnd",
    "dispute": "disp",
    "settlement": "setl",
    "payout": "pout",
    "payment_link": "plink",
    "customer": "cust",
    "fund_account": "fa",
    "contact": "cont",
    "invoice": "inv",
    "document": "doc",
    "support_message": "msg",
}


class IdFactory:
    """Generates Razorpay-shaped IDs from a seeded RNG."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def new(self, entity_type: str) -> str:
        try:
            prefix = PREFIXES[entity_type]
        except KeyError:
            raise ValueError(
                f"unknown entity type {entity_type!r}; known: {sorted(PREFIXES)}"
            ) from None
        body = "".join(self._rng.choices(ID_ALPHABET, k=ID_BODY_LENGTH))
        return f"{prefix}_{body}"


def entity_type_of(entity_id: str) -> str | None:
    """Recover the entity type from an ID, or None if the prefix is unknown."""
    prefix, sep, _ = entity_id.partition("_")
    if not sep:
        return None
    for entity_type, known_prefix in PREFIXES.items():
        if prefix == known_prefix:
            return entity_type
    return None
