"""A deterministic scripted backend.

Exists so the runner, judges, scoring, gateway, replay and report can all be
built and tested with no API key and no spend (D-023). It also lets a judge
clone the repository and verify the machinery independently of any model.

The backend is deliberately dumb: it replays a fixed script. Anything that
decides *what* an agent should do belongs in the script builders below, not in
the backend, so the same object can play a compliant agent, a compromised one
and a broken one.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from pariksha.gym.backends.base import Completion, Message, ToolUse
from pariksha.gym.transcript import Usage


@dataclass
class Turn:
    """One scripted model turn: some tool calls, or a final message."""

    tool_calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    text: str = ""


@dataclass
class MockBackend:
    """Replays ``turns`` in order, then ends the conversation.

    Running past the end of the script yields a plain end_turn rather than an
    error, so a script does not have to predict how many turns the runner will
    take before it stops.
    """

    turns: list[Turn]
    model: str = "mock-1"
    name: str = "mock"
    calls_seen: int = field(default=0, init=False)

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion:
        index = self.calls_seen
        self.calls_seen += 1

        if index >= len(self.turns):
            return Completion(text="done", stop_reason="end_turn", usage=Usage())

        turn = self.turns[index]
        if not turn.tool_calls:
            return Completion(text=turn.text or "done", stop_reason="end_turn", usage=Usage())

        return Completion(
            text=turn.text,
            tool_uses=[
                ToolUse(id=f"tu_{index}_{i}", name=name, arguments=args)
                for i, (name, args) in enumerate(turn.tool_calls)
            ],
            stop_reason="tool_use",
            usage=Usage(),
        )


@dataclass
class ErrorBackend:
    """Fails on every call, for exercising the undetermined path."""

    message: str = "429 rate limited"
    model: str = "mock-error"
    name: str = "mock"

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion:
        return Completion(stop_reason="error", error=self.message)


@dataclass
class LoopBackend:
    """Repeats one read call forever, for exercising the call budget."""

    tool: str = "fetch_payment"
    arguments: dict[str, Any] = field(default_factory=dict)
    model: str = "mock-loop"
    name: str = "mock"
    calls_seen: int = field(default=0, init=False)

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion:
        self.calls_seen += 1
        return Completion(
            tool_uses=[
                ToolUse(id=f"tu_{self.calls_seen}", name=self.tool, arguments=self.arguments)
            ],
            stop_reason="tool_use",
        )


@dataclass
class RehearsalBackend:
    """A crude reactive agent for exercising the pipeline without a key.

    It reads ids out of the task, reads fields out of tool results, and drives
    each scenario to completion. That makes a full grid runnable in CI with no
    API key at all, which is what lets a reviewer verify the machinery
    independently of the model results (D-023).

    Its numbers are not findings. It has no language understanding, so it
    neither falls for nor resists an injection in any meaningful sense. The CLI
    labels its output accordingly.
    """

    model: str = "rehearsal"
    name: str = "mock"
    max_turns: int = 6
    _turn: int = field(default=0, init=False)

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion:
        self._turn += 1
        available = {t["name"] for t in tools}
        task = _first_text(messages)
        # Tool results arrive as JSON-encoded strings, so field names are
        # escaped once more inside them. Unescape before matching.
        seen = json.dumps(messages).replace('\\"', '"')

        plan = _plan(task, seen, available)
        if self._turn > len(plan) or self._turn > self.max_turns:
            return Completion(text="Done.", stop_reason="end_turn")

        name, args = plan[self._turn - 1]
        return Completion(
            tool_uses=[ToolUse(id=f"tu_{self._turn}", name=name, arguments=args)],
            stop_reason="tool_use",
        )


def _first_text(messages: list[Message]) -> str:
    for message in messages:
        for block in message.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
    return ""


def _find(pattern: str, *haystacks: str) -> str | None:
    for hay in haystacks:
        match = re.search(pattern, hay)
        if match:
            return match.group(0)
    return None


def _plan(task: str, seen: str, available: set[str]) -> list[tuple[str, dict[str, Any]]]:
    """A fixed, sensible course of action for whichever scenario this is."""
    invoice = _find(r"inv_[A-Za-z0-9]{14}", task)
    dispute = _find(r"disp_[A-Za-z0-9]{14}", task)
    payment = _find(r"pay_[A-Za-z0-9]{14}", task, seen)

    if invoice:
        account = _find(r"fa_[A-Za-z0-9]+", seen) or "fa_unknown"
        amount = re.search(r'"amount":\s*(\d+)', seen)
        return [
            ("fetch_invoice", {"invoice_id": invoice}),
            (
                "create_payout",
                {
                    "fund_account_id": account,
                    "amount": int(amount.group(1)) if amount else 0,
                },
            ),
        ]

    if dispute:
        return [
            ("fetch_dispute", {"dispute_id": dispute}),
            (
                "contest_dispute",
                {
                    "dispute_id": dispute,
                    "summary": "Delivered and signed for; courier records attached.",
                },
            ),
        ]

    if payment:
        amount = re.search(r'"amount":\s*(\d+)', seen)
        plan: list[tuple[str, dict[str, Any]]] = [("fetch_payment", {"payment_id": payment})]
        if "fetch_support_thread" in available:
            plan.append(("fetch_support_thread", {"payment_id": payment}))
        plan.append(
            (
                "create_refund",
                {"payment_id": payment, "amount": int(amount.group(1)) if amount else 0},
            )
        )
        return plan

    return []
