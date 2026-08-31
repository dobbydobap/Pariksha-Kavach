"""Provenance tracking over tool results.

Driven by the schema registry (D-009): every value an agent sees is classified
by the field it arrived in. Trusted values came from Razorpay, a bank or a card
network; untrusted values were written by a customer, merchant or counterparty.

The enforceable consequence is narrow and precise. Attackers do not need the
agent to quote them; they need it to *act* on them, and acting means passing an
identifier into a money-moving argument. So the rule Kavach enforces is:

    only an identifier seen in a field Razorpay produced may receive money.

Stated positively on purpose. Asking "is it untrusted" let through an identifier
the tracker had never observed at all -- a hallucinated account number -- which
failed open on the one gate that spends money (D-081).

That kills destination diversion without any attempt to parse intent out of
prose, and it produces no false positive on a legitimate refund, because
``create_refund`` names a payment rather than a destination.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal

from pariksha.sandbox.entities import ENTITY_TYPES

Provenance = Literal["trusted", "untrusted", "unseen"]

# Identifier shapes an attacker would need the agent to act on: Razorpay entity
# ids and UPI VPAs. Free prose around them is irrelevant; only these can be
# passed into a destination argument.
IDENTIFIER = re.compile(
    r"\b(?:fa|pay|order|rfnd|pout|plink|cust|inv|disp|setl|cont)_[A-Za-z0-9]{6,}\b"
    r"|\b[A-Za-z0-9][\w.\-]{2,}@[a-z]{3,}\b"
)


@dataclass
class TaintTracker:
    """Accumulates the provenance of every identifier the agent has been shown."""

    trusted: set[str] = field(default_factory=set)
    untrusted: set[str] = field(default_factory=set)

    def observe(self, result: Any) -> None:
        """Record identifiers from one tool result, split by field provenance."""
        self._walk(result, entity=None, inherited_untrusted=False)

    def provenance_of(self, value: str) -> Provenance:
        """Classify an identifier. Trusted wins, because a value the agent saw in
        a trusted field is legitimate however else it also appeared."""
        if value in self.trusted:
            return "trusted"
        if value in self.untrusted:
            return "untrusted"
        return "unseen"

    def is_trusted(self, value: str) -> bool:
        """Only an identifier seen in a trusted field counts as verified.

        Deliberately not "is it untrusted": an identifier the tracker has never
        observed at all would then pass, which fails open. A hallucinated
        account number is exactly that case (D-081).
        """
        return self.provenance_of(value) == "trusted"

    def _walk(self, node: Any, entity: str | None, inherited_untrusted: bool) -> None:
        if isinstance(node, dict):
            entity = node.get("entity", entity) if isinstance(node.get("entity"), str) else entity
            untrusted_fields = self._untrusted_fields(entity)
            for key, value in node.items():
                tainted = inherited_untrusted or key in untrusted_fields
                self._walk(value, entity, tainted)
        elif isinstance(node, list):
            for item in node:
                self._walk(item, entity, inherited_untrusted)
        elif isinstance(node, str):
            self._record(node, inherited_untrusted)

    @staticmethod
    def _untrusted_fields(entity: str | None) -> frozenset[str]:
        model = ENTITY_TYPES.get(entity or "")
        return model.untrusted_fields() if model else frozenset()

    def _record(self, text: str, tainted: bool) -> None:
        target = self.untrusted if tainted else self.trusted
        for match in IDENTIFIER.findall(text):
            target.add(match)


# Arguments that name where money *goes*. Subject ids such as payment_id or
# dispute_id name what is being acted on, not where value lands, and a refund
# returns to the original instrument rather than anywhere the caller chooses.
# Including them here would block an agent for naming the record it was asked
# about, which is cost without security (D-084).
DESTINATION_ARGS = ("fund_account_id", "vpa")


def destinations_in(arguments: dict[str, Any]) -> list[tuple[str, str]]:
    """The (argument name, value) pairs of a call that name a target."""
    return [
        (name, value)
        for name, value in arguments.items()
        if name in DESTINATION_ARGS and isinstance(value, str)
    ]
