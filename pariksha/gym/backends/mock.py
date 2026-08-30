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
