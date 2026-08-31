"""Offline ablation: evaluate any policy against a recording, without a model.

Each episode is run live once with guardrails off. Every guardrail configuration
is then scored by replaying that recording through the policy engine, which
costs nothing (D-021, D-023).

Replay is honest about what it cannot know. See ``Fidelity``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from pariksha.gym.attacks import ATTACKS_BY_ID, apply
from pariksha.gym.transcript import Movement, ToolCall, Transcript
from pariksha.kavach.gateway import Kavach
from pariksha.kavach.policy import Policy
from pariksha.sandbox.seed import build
from pariksha.sandbox.state import RazorpayError
from pariksha.sandbox.tools import dispatch


class Fidelity(StrEnum):
    EXACT = "exact"
    """Nothing was blocked, so the replay is the original run.

    Kavach only ever blocks writes, never reads, so a run with no blocks leaves
    the agent's information state and the sandbox identical to the recording.
    """

    LOWER_BOUND = "lower_bound"
    """A call was blocked and further calls follow it.

    Everything after the first block is counterfactual: the sandbox diverged and
    the real agent would have seen an error it never actually saw. It might have
    retried by another route and succeeded, so true attack success under this
    policy is at least what the replay reports. Replay flatters the defense.
    """


@dataclass
class ReplayResult:
    transcript: Transcript
    fidelity: Fidelity
    blocked_calls: int

    @property
    def is_exact(self) -> bool:
        return self.fidelity is Fidelity.EXACT


def replay(recorded: Transcript, policy: Policy) -> ReplayResult:
    """Re-evaluate a recorded episode under ``policy``.

    The world is rebuilt from the transcript's scenario key and attack id rather
    than carried over, so determinism (D-011) is what makes this faithful.
    """
    scenario = build(recorded.scenario_key)
    attack = ATTACKS_BY_ID.get(recorded.attack_id or "")
    if attack is not None:
        scenario = apply(scenario, attack)

    kavach = Kavach(policy)
    allowed = set(recorded.tools)
    calls: list[ToolCall] = []
    first_block: int | None = None

    for original in recorded.calls:
        if allowed and original.name not in allowed:
            # Out of the agent's scope, exactly as the runner refused it (D-041).
            calls.append(
                ToolCall(
                    index=len(calls),
                    name=original.name,
                    arguments=original.arguments,
                    result=RazorpayError(
                        f"The requested URL was not found on the server: {original.name}",
                        code="NOT_FOUND_ERROR",
                    ).to_dict(),
                )
            )
            continue

        decision = kavach.check(original.name, original.arguments)

        if not decision.allow:
            if first_block is None:
                first_block = len(calls)
            calls.append(
                ToolCall(
                    index=len(calls),
                    name=original.name,
                    arguments=original.arguments,
                    result=RazorpayError(
                        f"Blocked by Kavach ({decision.defense}): {decision.reason}",
                        code="POLICY_DENIED",
                    ).to_dict(),
                    blocked=True,
                    block_reason=decision.reason,
                    blocked_by=decision.defense,
                )
            )
            continue

        result = dispatch(scenario.state, original.name, original.arguments)
        if "error" in result:
            kavach.observe(result)
        else:
            kavach.record_success(original.name, original.arguments, result)

        calls.append(
            ToolCall(
                index=len(calls),
                name=original.name,
                arguments=original.arguments,
                result=result,
            )
        )

    blocked = sum(1 for c in calls if c.blocked)
    diverged = first_block is not None and first_block < len(calls) - 1
    fidelity = Fidelity.LOWER_BOUND if diverged else Fidelity.EXACT

    transcript = Transcript(
        episode_id=recorded.episode_id,
        scenario_key=recorded.scenario_key,
        attack_id=recorded.attack_id,
        agent=recorded.agent,
        backend=recorded.backend,
        model=recorded.model,
        seed=recorded.seed,
        policy=policy.name,
        task=recorded.task,
        tools=recorded.tools,
        calls=calls,
        movements=[
            Movement(m.kind, m.entity_id, m.amount_paise, m.direction, m.destination)
            for m in scenario.state.movements
        ],
        final_text=recorded.final_text,
        stop_reason=recorded.stop_reason,
        usage=recorded.usage,
        error=recorded.error,
    )
    return ReplayResult(transcript=transcript, fidelity=fidelity, blocked_calls=blocked)


def replay_matrix(
    recorded: list[Transcript], policies: list[Policy]
) -> dict[str, list[ReplayResult]]:
    """Every recording against every policy, keyed by policy name.

    A fresh ``Kavach`` per episode per policy is essential: reusing one would
    carry spend totals and taint state across episodes and silently corrupt the
    table. ``replay`` constructs its own, so this stays a plain loop.
    """
    return {p.name: [replay(t, p) for t in recorded] for p in policies}


def fidelity_summary(results: list[ReplayResult]) -> dict[str, int]:
    """How much of a replayed column is exact rather than bounded."""
    return {
        "exact": sum(1 for r in results if r.is_exact),
        "lower_bound": sum(1 for r in results if not r.is_exact),
    }
