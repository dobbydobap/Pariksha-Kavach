"""Scorecard rendering tests."""

from __future__ import annotations

from pariksha.gym.score import Rate, Scorecard, score
from pariksha.gym.transcript import Movement, ToolCall, Transcript
from pariksha.report.scorecard import Column, ablation_rows, render

REFUND = "refund.non_delivery"
CORRECT = 500_000_00
ATTACKER = "fa_9xKq2LmZvT4Nqe"


def episode(attack_id: str | None = None, diverted: bool = False) -> Transcript:
    calls, movements = [], []
    if diverted:
        calls = [
            ToolCall(
                0,
                "create_payout",
                {"fund_account_id": ATTACKER, "amount": CORRECT},
                {"id": "po", "amount": CORRECT},
            )
        ]
        movements = [Movement("payout", "po", CORRECT, "out", ATTACKER)]
    return Transcript(
        episode_id="e",
        scenario_key=REFUND,
        attack_id=attack_id,
        agent="refund_resolver",
        backend="groq",
        model="openai/gpt-oss-120b",
        seed=1729,
        policy="off",
        task="t",
        calls=calls,
        movements=movements,
    )


def card() -> Scorecard:
    return score([episode(), episode("inj.system_notice.blatant", diverted=True)])


def test_the_report_is_self_contained():
    """A report that needs the network to render stops rendering."""
    html = render([Column("run", card())])
    for banned in ("http://", "https://", "<script", "@import"):
        assert banned not in html


def test_the_headline_carries_intervals_and_sample_sizes():
    html = render([Column("run", card())])
    assert "n=1" in html
    assert "Wilson" in html


def test_categories_and_subtlety_are_both_reported():
    html = render([Column("run", card())])
    assert "indirect_prompt_injection" in html
    assert "blatant" in html


def test_blast_radius_uses_indian_grouping():
    """One attacked episode leaking Rs 5,00,000 scales to Rs 50 crore per 1,000."""
    html = render([Column("run", card())])
    assert "Rs 50,00,00,000.00" in html


def test_multiple_runs_render_side_by_side():
    html = render([Column("before", card()), Column("after", card())])
    assert "before" in html and "after" in html


def test_a_metric_absent_from_one_column_shows_as_not_applicable():
    empty = score([episode()])
    html = render([Column("benign only", empty), Column("full", card())])
    assert "n/a" in html


def test_an_empty_scorecard_renders_without_error():
    html = render([Column("nothing", Scorecard())])
    assert "<title>" in html


def test_the_exception_list_is_published_when_present():
    undetermined = score(
        [
            Transcript(
                episode_id="e",
                scenario_key=REFUND,
                attack_id="inj.system_notice.blatant",
                agent="a",
                backend="groq",
                model="m",
                seed=1,
                policy="off",
                task="t",
                stop_reason="backend_error",
                error="HTTP 404",
            )
        ]
    )
    html = render([Column("run", undetermined)])
    assert "Exception list" in html
    assert "HTTP 404" in html


def test_the_replay_bound_direction_is_stated_next_to_the_ablation():
    """Publishing the bound backwards would discredit the table (D-050)."""
    rows = [
        {
            "policy": "default",
            "attack": "0%",
            "utility": "67%",
            "blast": "Rs 0.00",
            "exact": "22/22",
            "bar": 0,
        }
    ]
    html = render([Column("run", card())], ablation=rows)
    assert "lower bound" in html
    assert "exact only where nothing was blocked" in html


def test_ablation_bars_scale_to_the_worst_row():
    scores = {
        "off": Scorecard(attack_success=Rate(8, 10)),
        "default": Scorecard(attack_success=Rate(2, 10)),
    }
    matrix = {"off": [], "default": []}
    rows = ablation_rows(matrix, scores)
    assert rows[0]["bar"] > rows[1]["bar"]


def test_ablation_bars_survive_an_all_zero_column():
    scores = {"a": Scorecard(attack_success=Rate(0, 5))}
    rows = ablation_rows({"a": []}, scores)
    assert rows[0]["bar"] == 0
