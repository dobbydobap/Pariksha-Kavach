"""Rate limiting driven by the server's own accounting.

Groq reports the ceiling and the remaining budget on every response, so both
are knowable rather than estimated. A client-side rolling window has to guess
at each, and guessing conservatively costs wall-clock on every turn of every
episode (D-061).
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class RateLimit:
    """The provider's view of what budget is left, refreshed from each response."""

    limit_tokens: int | None = None
    remaining_tokens: int | None = None
    max_wait: float = 65.0

    def update(self, headers) -> None:
        limit = headers.get("x-ratelimit-limit-tokens")
        remaining = headers.get("x-ratelimit-remaining-tokens")

        if limit and limit.isdigit():
            self.limit_tokens = int(limit)
        if remaining and remaining.isdigit():
            self.remaining_tokens = int(remaining)

    def wait_for(self, forecast: int) -> float:
        """Sleep until ``forecast`` tokens plausibly fit. Returns seconds slept.

        The bucket refills continuously, so the wait is the shortfall divided by
        the refill rate rather than a fixed window. A forecast larger than the
        whole budget proceeds anyway: refusing it would stall the run forever,
        and the 429 path is the safety net.
        """
        if self.remaining_tokens is None or self.limit_tokens is None:
            return 0.0
        if forecast <= self.remaining_tokens or forecast > self.limit_tokens:
            return 0.0

        per_second = self.limit_tokens / 60
        shortfall = forecast - self.remaining_tokens
        pause = min(shortfall / per_second + 0.25, self.max_wait)
        time.sleep(pause)
        self.remaining_tokens = min(
            self.limit_tokens, self.remaining_tokens + int(pause * per_second)
        )
        return pause

    def spend(self, tokens: int) -> None:
        """Debit locally so consecutive calls pace before the next response lands."""
        if self.remaining_tokens is not None:
            self.remaining_tokens = max(0, self.remaining_tokens - tokens)
