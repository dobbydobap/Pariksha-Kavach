"""Agent definitions: a system prompt, a tool subset, and a call budget.

Tool scoping is an ablation dimension rather than a fixed choice (D-032), so an
agent carries the set it is allowed to see and variants differ only in that set.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pariksha.sandbox.tools import TOOLS_BY_NAME


@dataclass(frozen=True)
class AgentSpec:
    name: str
    system: str
    tools: tuple[str, ...]
    call_budget: int = 25

    def tool_definitions(self) -> list[dict[str, Any]]:
        try:
            return [TOOLS_BY_NAME[name] for name in self.tools]
        except KeyError as e:
            raise ValueError(f"agent {self.name!r} names an unknown tool: {e.args[0]}") from None

    def scoped_to(self, tools: tuple[str, ...]) -> AgentSpec:
        """A variant seeing only ``tools``, for the tool-scoping ablation."""
        return AgentSpec(
            name=f"{self.name}.scoped",
            system=self.system,
            tools=tools,
            call_budget=self.call_budget,
        )
