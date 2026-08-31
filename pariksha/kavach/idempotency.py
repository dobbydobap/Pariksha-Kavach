"""Duplicate-intent detection.

Agents do not supply idempotency keys, so the intent is fingerprinted instead:
the obligation being settled plus the amount. A second call with the same
fingerprint is a replay.

This is a blunt instrument by design and it has a real false-positive cost. Two
genuinely separate part-payments of equal size to the same vendor look identical
to it. That cost is not hidden -- it shows up as lost utility on the frontier,
which is the honest place for it.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

# The argument that identifies what is being settled, per money-moving tool.
OBLIGATION_ARG = {
    "create_refund": "payment_id",
    "create_payout": "fund_account_id",
    "accept_dispute": "dispute_id",
}


def fingerprint(name: str, arguments: dict[str, Any]) -> str | None:
    """A stable hash of one money-moving intent, or None if the tool moves none."""
    obligation = OBLIGATION_ARG.get(name)
    if obligation is None:
        return None
    body = json.dumps(
        {"tool": name, "target": arguments.get(obligation), "amount": arguments.get("amount")},
        sort_keys=True,
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]


@dataclass
class IdempotencyGuard:
    seen: set[str] = field(default_factory=set)

    def is_duplicate(self, name: str, arguments: dict[str, Any]) -> bool:
        return (fingerprint(name, arguments) or "") in self.seen

    def record(self, name: str, arguments: dict[str, Any]) -> None:
        key = fingerprint(name, arguments)
        if key:
            self.seen.add(key)
