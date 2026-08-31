"""Kavach: the enforcement point between an agent and Razorpay.

Composes taint tracking, policy, idempotency and the circuit breaker over a
hash-chained ledger. Every check is attributed to the defense that fired, which
is what makes the ablation table possible.

Kavach is given no ground truth (D-043). It sees only what a real deployment
would: the merchant's policy and the tool traffic itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from pariksha.kavach.breaker import CircuitBreaker
from pariksha.kavach.idempotency import IdempotencyGuard
from pariksha.kavach.ledger import Ledger
from pariksha.kavach.policy import Policy, contains_pii
from pariksha.kavach.taint import TaintTracker, destinations_in
from pariksha.sandbox.tools import MONEY_OUT_TOOLS, WRITE_TOOLS

# Fields whose contents leave the merchant's systems.
EGRESS_ARGS = {
    "contest_dispute": ("summary",),
    "create_payment_link": ("description",),
    "create_payout": ("narration",),
}


@dataclass(frozen=True)
class Decision:
    allow: bool
    reason: str | None = None
    defense: str | None = None

    @staticmethod
    def ok() -> Decision:
        return Decision(allow=True)

    @staticmethod
    def deny(defense: str, reason: str) -> Decision:
        return Decision(allow=False, defense=defense, reason=reason)


@dataclass
class Kavach:
    policy: Policy
    ledger: Ledger = field(default_factory=Ledger)
    taint: TaintTracker = field(default_factory=TaintTracker)
    idempotency: IdempotencyGuard = field(default_factory=IdempotencyGuard)
    reference_amounts: dict[str, int] = field(default_factory=dict)
    breaker: CircuitBreaker = field(init=False)
    spent_paise: int = 0

    def __post_init__(self) -> None:
        self.breaker = CircuitBreaker(max_denials=self.policy.breaker_max_denials)

    def observe(self, result: Any) -> None:
        """Feed a tool result into provenance tracking and amount references."""
        self.taint.observe(result)
        self._record_reference(result)

    def _record_reference(self, node: Any) -> None:
        """Remember what each entity is worth, so a 100x error has something to
        be measured against. Observed from ordinary traffic, not ground truth."""
        if isinstance(node, dict):
            entity_id, amount = node.get("id"), node.get("amount")
            if isinstance(entity_id, str) and isinstance(amount, int):
                self.reference_amounts[entity_id] = amount
            for value in node.values():
                self._record_reference(value)
        elif isinstance(node, list):
            for item in node:
                self._record_reference(item)

    def check(self, name: str, arguments: dict[str, Any]) -> Decision:
        """Decide whether one call may proceed, and record the decision."""
        decision = self._evaluate(name, arguments)
        self.ledger.append(
            "decision",
            {
                "tool": name,
                "arguments": arguments,
                "allow": decision.allow,
                "defense": decision.defense,
                "reason": decision.reason,
            },
        )
        if decision.allow:
            self.breaker.record_success()
        elif self.policy.has("breaker") and self.breaker.record_denial():
            self.ledger.append("breaker_tripped", {"after": name})
        return decision

    def record_success(self, name: str, arguments: dict[str, Any], result: Any) -> None:
        """Update spend and replay state after a call actually executed."""
        self.idempotency.record(name, arguments)
        if name in MONEY_OUT_TOOLS and isinstance(result, dict):
            amount = result.get("amount")
            if isinstance(amount, int):
                self.spent_paise += amount
        self.observe(result)

    def _evaluate(self, name: str, arguments: dict[str, Any]) -> Decision:
        if self.policy.has("breaker") and self.breaker.tripped:
            return Decision.deny("breaker", "agent suspended after repeated denials")

        if name not in WRITE_TOOLS:
            return Decision.ok()

        for gate in (
            self._destinations,
            self._spend,
            self._units,
            self._approval,
            self._idempotency,
            self._pii,
        ):
            decision = gate(name, arguments)
            if not decision.allow:
                return decision
        return Decision.ok()

    def _destinations(self, name: str, arguments: dict[str, Any]) -> Decision:
        if not self.policy.has("destinations"):
            return Decision.ok()

        for arg, value in destinations_in(arguments):
            if value in self.policy.destination_allowlist:
                continue
            if self.policy.require_trusted_destinations and self.taint.untrusted_only(value):
                return Decision.deny(
                    "destinations",
                    f"{arg}={value!r} has only ever appeared in untrusted data",
                )
        return Decision.ok()

    def _spend(self, name: str, arguments: dict[str, Any]) -> Decision:
        if not self.policy.has("spend"):
            return Decision.ok()

        amount = arguments.get("amount")
        if not isinstance(amount, int):
            return Decision.ok()

        cap = self.policy.per_call_paise.get(name)
        if cap is not None and amount > cap:
            return Decision.deny("spend", f"{name} of {amount} paise exceeds the cap of {cap}")

        total = self.policy.aggregate_paise
        if total is not None and name in MONEY_OUT_TOOLS and self.spent_paise + amount > total:
            return Decision.deny(
                "spend",
                f"aggregate {self.spent_paise + amount} paise exceeds the ceiling of {total}",
            )
        return Decision.ok()

    def _approval(self, name: str, arguments: dict[str, Any]) -> Decision:
        if not self.policy.has("approval"):
            return Decision.ok()

        threshold = self.policy.approval_threshold_paise
        amount = arguments.get("amount")
        if threshold is None or not isinstance(amount, int) or amount <= threshold:
            return Decision.ok()
        return Decision.deny(
            "approval", f"{amount} paise is above the {threshold} approval threshold"
        )

    def _idempotency(self, name: str, arguments: dict[str, Any]) -> Decision:
        if not self.policy.has("idempotency"):
            return Decision.ok()
        if self.idempotency.is_duplicate(name, arguments):
            return Decision.deny("idempotency", f"{name} repeats an already-settled obligation")
        return Decision.ok()

    def _units(self, name: str, arguments: dict[str, Any]) -> Decision:
        """A clean 100x gap against the entity being settled.

        Under-by-100x passes every spend cap and every destination check, so
        without this gate the silent paise error has no defense at all.
        """
        if not self.policy.has("units") or not self.policy.block_unit_confusion:
            return Decision.ok()

        amount = arguments.get("amount")
        reference = self.reference_amounts.get(str(arguments.get("payment_id")))
        if not isinstance(amount, int) or reference is None:
            return Decision.ok()

        if amount * 100 == reference or amount == reference * 100:
            return Decision.deny(
                "units",
                f"{amount} paise is a clean 100x from the {reference} paise it settles",
            )
        return Decision.ok()

    def _pii(self, name: str, arguments: dict[str, Any]) -> Decision:
        if not self.policy.has("pii") or not self.policy.block_pii_egress:
            return Decision.ok()

        for arg in EGRESS_ARGS.get(name, ()):
            value = arguments.get(arg)
            if isinstance(value, str) and (found := contains_pii(value)):
                return Decision.deny("pii", f"{found} detected in {name}.{arg}")
        return Decision.ok()
