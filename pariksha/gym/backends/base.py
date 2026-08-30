"""The model backend protocol.

Backends are swappable so the model is a parameter of the experiment rather
than a dependency of the harness (D-024).

The internal message format is Anthropic's content-block shape. Every provider
needs translating to or from something, and this shape is the most expressive
of the candidates, so it loses the least in translation: an OpenAI-compatible
backend flattens it, a Gemini backend renames it, and the Anthropic backend
passes it through.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

from pariksha.gym.transcript import Usage

Message = dict[str, Any]
StopReason = Literal["tool_use", "end_turn", "error"]


@dataclass
class ToolUse:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class Completion:
    text: str = ""
    tool_uses: list[ToolUse] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    stop_reason: StopReason = "end_turn"
    error: str | None = None


class Backend(Protocol):
    """Anything that can turn a conversation plus a tool surface into a turn."""

    name: str
    model: str

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion: ...


def assistant_message(completion: Completion) -> Message:
    """Render a completion back into the conversation."""
    content: list[dict[str, Any]] = []
    if completion.text:
        content.append({"type": "text", "text": completion.text})
    for use in completion.tool_uses:
        content.append({"type": "tool_use", "id": use.id, "name": use.name, "input": use.arguments})
    return {"role": "assistant", "content": content}


def tool_result_message(results: list[tuple[str, str]]) -> Message:
    """One user message carrying every tool result from the preceding turn.

    Results are batched into a single message because splitting them across
    several trains the model to stop making parallel calls.
    """
    return {
        "role": "user",
        "content": [
            {"type": "tool_result", "tool_use_id": use_id, "content": body}
            for use_id, body in results
        ],
    }
