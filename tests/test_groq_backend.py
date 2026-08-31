"""Groq backend tests. Translation and throttling only, no network."""

from __future__ import annotations

import json

import pytest

from pariksha.gym.backends.groq import (
    GroqBackend,
    TokenThrottle,
    to_openai_messages,
    to_openai_tools,
)
from pariksha.sandbox.tools import TOOLS


def test_tool_definitions_translate_to_the_openai_function_shape():
    translated = to_openai_tools(TOOLS[:2])
    assert all(t["type"] == "function" for t in translated)
    assert translated[0]["function"]["name"] == TOOLS[0]["name"]
    assert translated[0]["function"]["parameters"] == TOOLS[0]["input_schema"]


def test_strictness_survives_translation():
    """additionalProperties: false is what makes a malformed call
    unrepresentable (D-014); losing it in translation would quietly weaken it."""
    for t in to_openai_tools(TOOLS):
        assert t["function"]["parameters"]["additionalProperties"] is False


def test_system_prompt_becomes_the_first_message():
    out = to_openai_messages("be careful", [])
    assert out == [{"role": "system", "content": "be careful"}]


def test_user_text_flattens():
    out = to_openai_messages(
        "s", [{"role": "user", "content": [{"type": "text", "text": "do the thing"}]}]
    )
    assert out[1] == {"role": "user", "content": "do the thing"}


def test_assistant_tool_use_becomes_tool_calls_with_json_arguments():
    out = to_openai_messages(
        "s",
        [
            {
                "role": "assistant",
                "content": [
                    {"type": "text", "text": "checking"},
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "fetch_payment",
                        "input": {"payment_id": "pay_1"},
                    },
                ],
            }
        ],
    )
    message = out[1]
    assert message["role"] == "assistant"
    assert message["content"] == "checking"
    call = message["tool_calls"][0]
    assert call["id"] == "tu_1"
    assert call["function"]["name"] == "fetch_payment"
    assert json.loads(call["function"]["arguments"]) == {"payment_id": "pay_1"}


def test_a_batch_of_tool_results_expands_to_one_message_each():
    """Internally a batch is one message (D-040); OpenAI needs one per result."""
    out = to_openai_messages(
        "s",
        [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": "tu_1", "content": "{}"},
                    {"type": "tool_result", "tool_use_id": "tu_2", "content": "{}"},
                ],
            }
        ],
    )
    assert [m["role"] for m in out[1:]] == ["tool", "tool"]
    assert [m["tool_call_id"] for m in out[1:]] == ["tu_1", "tu_2"]


def test_an_assistant_turn_with_no_text_sends_null_content():
    out = to_openai_messages(
        "s",
        [
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "t", "name": "fetch_payment", "input": {}}],
            }
        ],
    )
    assert out[1]["content"] is None


def test_a_full_exchange_round_trips_in_order():
    out = to_openai_messages(
        "s",
        [
            {"role": "user", "content": [{"type": "text", "text": "task"}]},
            {
                "role": "assistant",
                "content": [{"type": "tool_use", "id": "t1", "name": "fetch_payment", "input": {}}],
            },
            {
                "role": "user",
                "content": [{"type": "tool_result", "tool_use_id": "t1", "content": "{}"}],
            },
        ],
    )
    assert [m["role"] for m in out] == ["system", "user", "assistant", "tool"]


# ---------------------------------------------------------------------------
# Throttle
# ---------------------------------------------------------------------------


def test_the_throttle_lets_traffic_under_the_ceiling_straight_through():
    t = TokenThrottle(tokens_per_minute=6000)
    t.record(1000)
    assert t.wait_for(1000) == 0.0


def test_the_throttle_does_not_deadlock_on_an_oversized_single_request():
    """One request larger than the whole window must proceed, not hang."""
    t = TokenThrottle(tokens_per_minute=100)
    assert t.wait_for(500) == 0.0


def test_spend_ages_out_of_the_window():
    import time as clock

    t = TokenThrottle(tokens_per_minute=6000)
    t._window.append((clock.monotonic() - 120, 5000))
    assert t.wait_for(5000) == 0.0


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


def test_a_missing_key_fails_loudly_with_the_signup_url(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="console.groq.com"):
        GroqBackend()


def test_an_unknown_model_is_rejected_before_any_request(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    with pytest.raises(ValueError, match="unknown Groq model"):
        GroqBackend(model="gpt-4")


def test_the_backend_reports_its_identity(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    b = GroqBackend(model="qwen/qwen3.8-27b")
    assert (b.name, b.model) == ("groq", "qwen/qwen3.8-27b")
