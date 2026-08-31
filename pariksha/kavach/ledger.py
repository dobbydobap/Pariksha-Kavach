"""Hash-chained append-only audit log.

Every entry commits to its predecessor, so altering or removing any past entry
invalidates every hash after it. Tampering is detectable rather than merely
discouraged, which is what separates an audit trail from a log file.

The chain is also what makes free offline ablation possible: a verified entry
sequence is a faithful replay of what the agent did (D-021).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any

GENESIS = "0" * 64


@dataclass(frozen=True)
class Entry:
    index: int
    at: int
    kind: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str


def _digest(index: int, at: int, kind: str, payload: dict[str, Any], prev_hash: str) -> str:
    body = json.dumps(
        {"index": index, "at": at, "kind": kind, "payload": payload, "prev_hash": prev_hash},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


@dataclass
class Ledger:
    entries: list[Entry] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.entries[-1].hash if self.entries else GENESIS

    def append(self, kind: str, payload: dict[str, Any], at: int = 0) -> Entry:
        index = len(self.entries)
        prev = self.head
        entry = Entry(
            index=index,
            at=at,
            kind=kind,
            payload=payload,
            prev_hash=prev,
            hash=_digest(index, at, kind, payload, prev),
        )
        self.entries.append(entry)
        return entry

    def verify(self) -> tuple[bool, int | None]:
        """Recompute the chain. Returns (ok, index of the first bad entry)."""
        prev = GENESIS
        for entry in self.entries:
            expected = _digest(entry.index, entry.at, entry.kind, entry.payload, entry.prev_hash)
            if entry.prev_hash != prev or entry.hash != expected:
                return False, entry.index
            prev = entry.hash
        return True, None

    def of_kind(self, kind: str) -> list[Entry]:
        return [e for e in self.entries if e.kind == kind]

    def to_json(self) -> str:
        return json.dumps([asdict(e) for e in self.entries], ensure_ascii=False)
