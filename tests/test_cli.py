"""CLI tests. No network, no model calls."""

from __future__ import annotations

import pytest
import typer
from typer.testing import CliRunner

from pariksha.agents.catalogue import AGENTS, MINIMAL_TOOLS
from pariksha.cli.main import app, make_backend, make_policy
from pariksha.gym.attacks import ALL_ATTACKS
from pariksha.gym.grid import VARIANTS, agent_variant, build_grid
from pariksha.kavach.policy import DEFENSES
from pariksha.sandbox.seed import SCENARIOS

runner = CliRunner()


# ---------------------------------------------------------------------------
# Grid
# ---------------------------------------------------------------------------


def test_the_grid_is_one_control_per_scenario_plus_every_attack():
    grid = build_grid()
    assert len(grid) == len(SCENARIOS) + sum(len(a.applies_to) for a in ALL_ATTACKS)
    assert sum(1 for e in grid if e.attack is None) == len(SCENARIOS)


def test_every_episode_gets_the_agent_that_owns_its_scenario():
    for e in build_grid():
        assert e.agent.name.startswith(
            {"refund": "refund", "dispute": "dispute", "payout": "payout"}[
                e.scenario_key.split(".")[0]
            ]
        )


def test_variants_change_the_agent_and_nothing_about_coverage():
    base = build_grid("base")
    for variant in VARIANTS:
        grid = build_grid(variant)
        assert len(grid) == len(base)
        assert [e.label for e in grid] == [e.label for e in base]


def test_the_scoped_variant_narrows_the_tool_set():
    scoped = agent_variant(AGENTS["refund_resolver"], "scoped")
    assert scoped.tools == MINIMAL_TOOLS["refund_resolver"]


def test_the_hardened_scoped_variant_applies_both():
    both = agent_variant(AGENTS["refund_resolver"], "hardened+scoped")
    assert both.tools == MINIMAL_TOOLS["refund_resolver"]
    assert "not instruction" in both.system


def test_an_unknown_variant_is_rejected():
    with pytest.raises(ValueError, match="unknown variant"):
        agent_variant(AGENTS["refund_resolver"], "nonsense")


def test_episode_labels_distinguish_control_from_attack():
    grid = build_grid()
    assert any(e.label.endswith("/benign") for e in grid)
    assert any(e.label.endswith("/inj.system_notice.blatant") for e in grid)


# ---------------------------------------------------------------------------
# Resolvers
# ---------------------------------------------------------------------------


def test_policy_names_resolve():
    assert make_policy("off").enabled == frozenset()
    assert make_policy("default").has("spend")
    assert not make_policy("no-spend").has("spend")
    assert make_policy("only-pii").has("pii")
    assert not make_policy("only-pii").has("spend")


def test_every_defense_has_a_no_form():
    for d in DEFENSES:
        assert not make_policy(f"no-{d}").has(d)


def test_bad_policy_names_are_rejected():
    for name in ("nonsense", "no-nonsense"):
        with pytest.raises((typer.BadParameter, ValueError)):
            make_policy(name)


def test_the_mock_backend_is_refused_for_whole_runs():
    """It is scripted per episode, so it cannot drive a grid."""
    with pytest.raises(typer.BadParameter, match="cannot drive a whole run"):
        make_backend("mock", "mock-1")


def test_unknown_backends_are_rejected():
    with pytest.raises(typer.BadParameter, match="unknown backend"):
        make_backend("openai", "gpt-4")


def test_groq_without_a_key_fails_with_guidance(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="console.groq.com"):
        make_backend("groq", "llama-3.3-70b-versatile")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def test_corpus_reports_coverage():
    result = runner.invoke(app, ["corpus"])
    assert result.exit_code == 0
    assert "rbi_compliance" in result.stdout
    assert "22 episodes" in result.stdout


def test_policy_command_prints_resolved_json():
    result = runner.invoke(app, ["policy", "default"])
    assert result.exit_code == 0
    assert "approval_threshold_paise" in result.stdout


def test_rescore_on_a_missing_run_fails_cleanly():
    result = runner.invoke(app, ["rescore", "does-not-exist"])
    assert result.exit_code != 0


def test_ablate_on_a_missing_run_fails_cleanly():
    result = runner.invoke(app, ["ablate", "does-not-exist"])
    assert result.exit_code != 0
