"""Circuit breaker on repeated policy denials.

One denial is an agent making a mistake. A run of them is an agent under
adversarial control, still trying. The breaker converts that pattern into a stop
rather than letting the agent keep probing until something gets through.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CircuitBreaker:
    max_denials: int | None = 3
    denials: int = 0
    tripped: bool = False

    def record_denial(self) -> bool:
        """Count a denial. Returns True if this one tripped the breaker."""
        if self.max_denials is None or self.tripped:
            return False
        self.denials += 1
        if self.denials >= self.max_denials:
            self.tripped = True
            return True
        return False

    def record_success(self) -> None:
        """A clean call resets the streak; the breaker targets runs, not totals."""
        self.denials = 0
