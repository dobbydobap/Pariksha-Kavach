"""Episode records: the artefact judging, replay and scoring all read.

One JSONL line per episode under ``runs/<run_id>/episodes.jsonl``. Everything
needed to re-judge or re-ablate an episode without re-running the model is in
the line, which is what makes offline ablation possible (D-021).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

StopReason = Literal["completed", "budget_exhausted", "backend_error", "no_tool_use"]


@dataclass
class ToolCall:
    """One tool invocation and what came back.

    ``blocked`` records a gateway refusal. The arguments are kept even when
    blocked, because what the agent *tried* to do is the interesting signal.
    """

    index: int
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    blocked: bool = False
    block_reason: str | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            self.input_tokens + other.input_tokens,
            self.output_tokens + other.output_tokens,
            self.cache_read_tokens + other.cache_read_tokens,
            self.cache_write_tokens + other.cache_write_tokens,
        )


@dataclass
class Movement:
    """A money movement copied out of the sandbox at episode end."""

    kind: str
    entity_id: str
    amount_paise: int
    direction: str
    destination: str | None


@dataclass
class Transcript:
    episode_id: str
    scenario_key: str
    attack_id: str | None
    agent: str
    backend: str
    model: str
    seed: int
    policy: str
    task: str
    calls: list[ToolCall] = field(default_factory=list)
    movements: list[Movement] = field(default_factory=list)
    final_text: str = ""
    stop_reason: StopReason = "completed"
    usage: Usage = field(default_factory=Usage)
    error: str | None = None

    @property
    def is_benign(self) -> bool:
        return self.attack_id is None

    @property
    def money_out_paise(self) -> int:
        return sum(m.amount_paise for m in self.movements if m.direction == "out")

    def calls_to(self, tool_name: str) -> list[ToolCall]:
        return [c for c in self.calls if c.name == tool_name]

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, line: str) -> Transcript:
        raw = json.loads(line)
        return cls(
            **{
                **raw,
                "calls": [ToolCall(**c) for c in raw["calls"]],
                "movements": [Movement(**m) for m in raw["movements"]],
                "usage": Usage(**raw["usage"]),
            }
        )


def episode_id(scenario_key: str, attack_id: str | None, model: str, policy: str) -> str:
    """Stable identifier for one cell of the experiment grid."""
    return f"{scenario_key}|{attack_id or 'benign'}|{model}|{policy}"


def run_id(seed: int, backend: str, model: str, policy: str) -> str:
    """Directory name for a run. Deterministic, so re-runs overwrite in place."""
    safe_model = model.replace("/", "-").replace(":", "-")
    return f"{seed}-{backend}-{safe_model}-{policy}"


class TranscriptWriter:
    """Appends episodes to ``runs/<run_id>/episodes.jsonl``."""

    def __init__(self, root: Path, run: str) -> None:
        self.dir = root / run
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "episodes.jsonl"
        self.path.write_text("", encoding="utf-8")

    def write(self, transcript: Transcript) -> None:
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(transcript.to_json() + "\n")


def read_transcripts(path: Path) -> Iterator[Transcript]:
    """Stream episodes from a JSONL file, skipping blank lines."""
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                yield Transcript.from_json(line)
