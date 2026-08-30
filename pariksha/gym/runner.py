"""Episode execution: drive a backend against the sandbox and record what happened."""

from __future__ import annotations

import json

from pariksha.agents.base import AgentSpec
from pariksha.gym.attacks import Attack, apply
from pariksha.gym.backends.base import Backend, assistant_message, tool_result_message
from pariksha.gym.transcript import Movement, ToolCall, Transcript, Usage, episode_id
from pariksha.sandbox.seed import Scenario
from pariksha.sandbox.state import RazorpayError
from pariksha.sandbox.tools import dispatch


def run_episode(
    scenario: Scenario,
    agent: AgentSpec,
    backend: Backend,
    attack: Attack | None = None,
    policy: str = "off",
) -> Transcript:
    """Run one episode to completion and return its transcript.

    The attack is applied here rather than by the caller so the transcript's
    metadata cannot drift out of sync with the state the agent actually saw.
    """
    sc = apply(scenario, attack) if attack else scenario
    tool_defs = agent.tool_definitions()
    allowed = set(agent.tools)

    messages = [{"role": "user", "content": [{"type": "text", "text": sc.task}]}]
    calls: list[ToolCall] = []
    usage = Usage()
    final_text = ""
    error: str | None = None

    while True:
        if len(calls) >= agent.call_budget:
            stop_reason = "budget_exhausted"
            break

        completion = backend.complete(agent.system, messages, tool_defs)
        usage = usage + completion.usage

        if completion.stop_reason == "error":
            stop_reason = "backend_error"
            error = completion.error
            break

        if not completion.tool_uses:
            final_text = completion.text
            stop_reason = "completed" if calls else "no_tool_use"
            break

        messages.append(assistant_message(completion))

        results: list[tuple[str, str]] = []
        for use in completion.tool_uses:
            if len(calls) >= agent.call_budget:
                break
            result = _invoke(sc, use.name, use.arguments, allowed)
            calls.append(
                ToolCall(
                    index=len(calls),
                    name=use.name,
                    arguments=use.arguments,
                    result=result,
                )
            )
            results.append((use.id, json.dumps(result, ensure_ascii=False)))

        messages.append(tool_result_message(results))

    return Transcript(
        episode_id=episode_id(sc.key, attack.id if attack else None, backend.model, policy),
        scenario_key=sc.key,
        attack_id=attack.id if attack else None,
        agent=agent.name,
        backend=backend.name,
        model=backend.model,
        seed=sc.state.seed,
        policy=policy,
        task=sc.task,
        calls=calls,
        movements=[
            Movement(m.kind, m.entity_id, m.amount_paise, m.direction, m.destination)
            for m in sc.state.movements
        ],
        final_text=final_text,
        stop_reason=stop_reason,  # type: ignore[arg-type]
        usage=usage,
        error=error,
    )


def _invoke(scenario: Scenario, name: str, args: dict, allowed: set[str]) -> dict:
    """Dispatch one call, refusing tools outside the agent's scope.

    A scoped agent that reaches for a tool it was not given must see the same
    404 a real API would return, otherwise the tool-scoping ablation would
    measure nothing.
    """
    if name not in allowed:
        return RazorpayError(
            f"The requested URL was not found on the server: {name}",
            code="NOT_FOUND_ERROR",
        ).to_dict()
    return dispatch(scenario.state, name, args)
