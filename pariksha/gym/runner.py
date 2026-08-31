"""Episode execution: drive a backend against the sandbox and record what happened."""

from __future__ import annotations

import json

from pariksha.agents.base import AgentSpec
from pariksha.gym.attacks import Attack, apply
from pariksha.gym.backends.base import Backend, assistant_message, tool_result_message
from pariksha.gym.transcript import Movement, ToolCall, Transcript, Usage, episode_id
from pariksha.kavach.gateway import Decision, Kavach
from pariksha.sandbox.seed import Scenario
from pariksha.sandbox.state import RazorpayError
from pariksha.sandbox.tools import dispatch


def run_episode(
    scenario: Scenario,
    agent: AgentSpec,
    backend: Backend,
    attack: Attack | None = None,
    kavach: Kavach | None = None,
) -> Transcript:
    """Run one episode to completion and return its transcript.

    The attack is applied here rather than by the caller so the transcript's
    metadata cannot drift out of sync with the state the agent actually saw.
    """
    sc = apply(scenario, attack) if attack else scenario
    policy = kavach.policy.name if kavach else "off"
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
            result, block = _invoke(sc, use.name, use.arguments, allowed, kavach)
            calls.append(
                ToolCall(
                    index=len(calls),
                    name=use.name,
                    arguments=use.arguments,
                    result=result,
                    blocked=block is not None,
                    block_reason=block.reason if block else None,
                    blocked_by=block.defense if block else None,
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
        tools=list(agent.tools),
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


def _invoke(
    scenario: Scenario,
    name: str,
    args: dict,
    allowed: set[str],
    kavach: Kavach | None,
) -> tuple[dict, Decision | None]:
    """Dispatch one call through the gateway. Returns (result, blocking decision).

    A tool outside the agent's scope sees the same 404 a real API would return,
    otherwise the tool-scoping ablation would measure nothing (D-041). A gateway
    refusal is surfaced as an error body too, so the agent gets the chance to
    recover the way it would in production.
    """
    if name not in allowed:
        error = RazorpayError(
            f"The requested URL was not found on the server: {name}",
            code="NOT_FOUND_ERROR",
        ).to_dict()
        return error, None

    if kavach is not None:
        decision = kavach.check(name, args)
        if not decision.allow:
            error = RazorpayError(
                f"Blocked by Kavach ({decision.defense}): {decision.reason}",
                code="POLICY_DENIED",
            ).to_dict()
            return error, decision

    result = dispatch(scenario.state, name, args)

    if kavach is not None:
        if "error" in result:
            kavach.observe(result)
        else:
            kavach.record_success(name, args, result)

    return result, None
