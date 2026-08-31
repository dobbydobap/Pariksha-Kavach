"""Groq backend. Free tier, no card, two model families from one key.

Groq speaks the OpenAI chat-completions shape, so this is mostly translation
from the internal content-block format (D-039). Raw httpx rather than an SDK:
one endpoint, one request shape, and no dependency added for it.

The binding constraint is tokens per minute, not requests per day. Without
prompt caching the whole prompt is billed every turn, so pacing is what keeps a
long run alive. The ceiling and the remaining budget come from the provider's
own response headers rather than a client-side guess (D-061).
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

from pariksha.gym.backends.base import Completion, Message, ToolUse
from pariksha.gym.backends.throttle import RateLimit
from pariksha.gym.transcript import Usage

ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"

# Confirmed against GET /openai/v1/models rather than assumed; Groq's
# catalogue moves and a stale id costs a whole run (D-059).
MODELS = {
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3.8-27b",
    "qwen/qwen3.6-27b",
}


def to_openai_tools(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t["description"],
                "parameters": t["input_schema"],
            },
        }
        for t in tools
    ]


def to_openai_messages(system: str, messages: list[Message]) -> list[dict[str, Any]]:
    """Flatten content blocks into the OpenAI wire shape.

    One difference matters: a batch of tool results is a single message
    internally (D-040) but OpenAI requires one ``tool`` message per result, so
    the batch is expanded here and only here.
    """
    out: list[dict[str, Any]] = [{"role": "system", "content": system}]

    for message in messages:
        blocks = message["content"]
        role = message["role"]

        if role == "user":
            results = [b for b in blocks if b.get("type") == "tool_result"]
            if results:
                out.extend(
                    {
                        "role": "tool",
                        "tool_call_id": b["tool_use_id"],
                        "content": b["content"],
                    }
                    for b in results
                )
            else:
                text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
                out.append({"role": "user", "content": text})
            continue

        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        tool_calls = [
            {
                "id": b["id"],
                "type": "function",
                "function": {"name": b["name"], "arguments": json.dumps(b["input"])},
            }
            for b in blocks
            if b.get("type") == "tool_use"
        ]
        entry: dict[str, Any] = {"role": "assistant", "content": text or None}
        if tool_calls:
            entry["tool_calls"] = tool_calls
        out.append(entry)

    return out


@dataclass
class GroqBackend:
    model: str = "openai/gpt-oss-120b"
    name: str = "groq"
    api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    temperature: float = 0.0
    max_tokens: int = 900
    timeout: float = 120.0
    limit: RateLimit = field(default_factory=RateLimit)
    max_retries: int = 4
    _observed_output: int = field(default=250, init=False)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Get a free key at https://console.groq.com "
                "and put it in .env"
            )
        if self.model not in MODELS:
            raise ValueError(f"unknown Groq model {self.model!r}; known: {sorted(MODELS)}")
        self._client = httpx.Client(timeout=self.timeout)

    def complete(
        self, system: str, messages: list[Message], tools: list[dict[str, Any]]
    ) -> Completion:
        body = {
            "model": self.model,
            "messages": to_openai_messages(system, messages),
            "tools": to_openai_tools(tools),
            "tool_choice": "auto",
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

        # Forecast on observed output, not max_tokens. Budgeting for the
        # worst case on every turn triples wall-clock for no benefit; a rare
        # underestimate is absorbed by the 429 path.
        forecast = len(json.dumps(body)) // 4 + self._observed_output
        self.limit.wait_for(forecast)
        self.limit.spend(forecast)

        payload = self._post(body)
        if isinstance(payload, Completion):
            return payload

        usage_raw = payload.get("usage") or {}
        usage = Usage(
            input_tokens=usage_raw.get("prompt_tokens", 0),
            output_tokens=usage_raw.get("completion_tokens", 0),
        )
        self._observed_output = max(self._observed_output, usage_raw.get("completion_tokens", 0))

        message = (payload.get("choices") or [{}])[0].get("message") or {}
        tool_uses = []
        for call in message.get("tool_calls") or []:
            fn = call.get("function") or {}
            try:
                arguments = json.loads(fn.get("arguments") or "{}")
            except json.JSONDecodeError:
                # A schema-valid call is what we want to measure; malformed JSON
                # is the model failing to emit a call at all, not being
                # manipulated into a harmful one (D-014).
                continue
            tool_uses.append(
                ToolUse(id=call.get("id", ""), name=fn.get("name", ""), arguments=arguments)
            )

        return Completion(
            text=message.get("content") or "",
            tool_uses=tool_uses,
            usage=usage,
            stop_reason="tool_use" if tool_uses else "end_turn",
        )

    def _post(self, body: dict[str, Any]) -> dict[str, Any] | Completion:
        """POST with backoff on rate limits. Returns a Completion on give-up."""
        headers = {"Authorization": f"Bearer {self.api_key}"}
        last = ""

        for attempt in range(self.max_retries):
            try:
                response = self._client.post(ENDPOINT, json=body, headers=headers)
            except httpx.HTTPError as e:
                last = f"transport error: {e}"
                time.sleep(2**attempt)
                continue

            self.limit.update(response.headers)

            if response.status_code == 200:
                return response.json()

            last = f"HTTP {response.status_code}: {response.text[:200]}"
            if response.status_code == 429:
                time.sleep(float(response.headers.get("retry-after", 2**attempt)))
                continue
            if response.status_code >= 500:
                time.sleep(2**attempt)
                continue
            break

        # An episode that could not be run is undetermined, never a pass (D-038).
        return Completion(stop_reason="error", error=last)
