"""The experiment grid: which agent runs which scenario against which attack.

One benign control per scenario plus one episode per applicable attack, so
every adversarial run has a baseline differing in exactly one variable (D-015).
"""

from __future__ import annotations

from dataclasses import dataclass

from pariksha.agents.base import AgentSpec
from pariksha.agents.catalogue import AGENT_FOR_SCENARIO, hardened, scoped
from pariksha.gym.attacks import Attack, attacks_for
from pariksha.sandbox.seed import SCENARIOS

VARIANTS = ("base", "hardened", "scoped", "hardened+scoped")


@dataclass(frozen=True)
class Episode:
    scenario_key: str
    agent: AgentSpec
    attack: Attack | None = None

    @property
    def label(self) -> str:
        return f"{self.scenario_key}/{self.attack.id if self.attack else 'benign'}"


def agent_variant(spec: AgentSpec, variant: str) -> AgentSpec:
    if variant == "base":
        return spec
    if variant == "hardened":
        return hardened(spec)
    if variant == "scoped":
        return scoped(spec)
    if variant == "hardened+scoped":
        return scoped(hardened(spec))
    raise ValueError(f"unknown variant {variant!r}; known: {VARIANTS}")


def build_grid(variant: str = "base") -> list[Episode]:
    episodes: list[Episode] = []
    for key in SCENARIOS:
        agent = agent_variant(AGENT_FOR_SCENARIO[key], variant)
        episodes.append(Episode(key, agent))
        episodes.extend(Episode(key, agent, attack) for attack in attacks_for(key))
    return episodes
