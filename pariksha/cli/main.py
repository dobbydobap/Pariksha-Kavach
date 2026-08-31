"""The pariksha command line."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from pariksha.gym.backends.groq import DailyBudgetExhausted
from pariksha.gym.grid import VARIANTS, build_grid
from pariksha.gym.runner import run_episode
from pariksha.gym.score import Scorecard, score
from pariksha.gym.transcript import TranscriptWriter, read_transcripts, run_id
from pariksha.kavach.gateway import Kavach
from pariksha.kavach.policy import DEFENSES, Policy, default_policy
from pariksha.kavach.replay import fidelity_summary, replay_matrix
from pariksha.sandbox.money import format_inr
from pariksha.sandbox.seed import build

# Keys live in .env; backends read them from the environment.
load_dotenv()

app = typer.Typer(add_completion=False, help="An exam for money-moving AI agents.")
console = Console()
RUNS = Path("runs")
REPORT = Path("report_out")


def make_backend(name: str, model: str):
    if name == "mock":
        raise typer.BadParameter(
            "the mock backend is scripted per episode and cannot drive a whole run; "
            "it is used by the test suite"
        )
    if name == "groq":
        from pariksha.gym.backends.groq import GroqBackend

        return GroqBackend(model=model)
    raise typer.BadParameter(f"unknown backend {name!r}; known: mock, groq")


def make_policy(name: str) -> Policy:
    if name == "off":
        return Policy.off()
    if name == "default":
        return default_policy()
    if name.startswith("no-"):
        return default_policy().without(name.removeprefix("no-"))
    if name.startswith("only-"):
        return default_policy().only(name.removeprefix("only-"))
    raise typer.BadParameter(f"unknown policy {name!r}; try off, default, no-<defense>")


def render(card: Scorecard, title: str) -> None:
    table = Table(title=title, title_justify="left")
    table.add_column("metric")
    table.add_column("value", justify="right")

    table.add_row("episodes", str(card.episodes))
    table.add_row("attack success", str(card.attack_success))
    table.add_row("any violation", str(card.any_violation))
    table.add_row("benign utility", str(card.benign_utility))
    table.add_row("utility under attack", str(card.attacked_utility))
    table.add_row("escalated to a human", str(card.escalation))
    table.add_row("blast radius / 1000 episodes", format_inr(card.blast_radius_paise_per_1000))
    table.add_row("undetermined", str(card.undetermined))
    console.print(table)

    if card.by_category:
        cats = Table(title="attack success by category", title_justify="left")
        cats.add_column("category")
        cats.add_column("rate", justify="right")
        for name, rate in card.by_category.items():
            cats.add_row(name, str(rate))
        console.print(cats)

    if card.exceptions:
        console.print("\n[bold]exception list[/bold] (neither passed nor failed)")
        for e in card.exceptions:
            console.print(f"  {e.attack_id or 'benign':<34} {e.reason}")


@app.command()
def bench(
    seed: int = typer.Option(1729, help="Reproduces the whole run."),
    backend: str = typer.Option("groq", help="Model backend."),
    model: str = typer.Option("openai/gpt-oss-120b", help="Model id."),
    policy: str = typer.Option("off", help="off, default, no-<defense>, only-<defense>."),
    variant: str = typer.Option("base", help=f"Agent variant: {', '.join(VARIANTS)}."),
    limit: int = typer.Option(0, help="Stop after N episodes. 0 runs the whole grid."),
) -> None:
    """Run the benchmark and write transcripts under runs/."""
    episodes = build_grid(variant, seed=seed)
    if limit:
        episodes = episodes[:limit]

    driver = make_backend(backend, model)
    guard = make_policy(policy)
    run = run_id(seed, backend, model, guard.name)
    writer = TranscriptWriter(RUNS, run)

    console.print(f"[bold]{len(episodes)}[/bold] episodes -> runs/{run}\n")
    transcripts = []
    stopped = None

    with console.status("") as status:
        for i, episode in enumerate(episodes, 1):
            status.update(f"[{i}/{len(episodes)}] {episode.label}")
            scenario = build(episode.scenario_key, seed=seed)
            kavach = Kavach(guard) if guard.enabled else None
            try:
                t = run_episode(scenario, episode.agent, driver, episode.attack, kavach)
            except DailyBudgetExhausted as e:
                stopped = f"{e}  Stopped after {i - 1} of {len(episodes)} episodes."
                break
            writer.write(t)
            transcripts.append(t)

    if stopped:
        console.print(f"[yellow]budget[/yellow] {stopped}\n")

    card = score(transcripts)
    render(card, f"{backend}/{model}  policy={guard.name}  variant={variant}")

    tokens = sum(t.usage.input_tokens + t.usage.output_tokens for t in transcripts)
    console.print(f"\n{tokens:,} tokens across {len(transcripts)} episodes")


@app.command()
def rehearse(
    seed: int = typer.Option(1729),
    policy: str = typer.Option("off"),
    variant: str = typer.Option("base"),
) -> None:
    """Run the whole grid with no API key, to prove the pipeline works.

    The rehearsal agent has no language understanding, so it neither falls for
    nor resists an injection. The numbers below exercise the machinery and are
    not findings.
    """
    from pariksha.gym.backends.mock import RehearsalBackend

    episodes = build_grid(variant)
    guard = make_policy(policy)
    run = run_id(seed, "rehearsal", "rehearsal", guard.name)
    writer = TranscriptWriter(RUNS, run)

    transcripts = []
    for episode in episodes:
        scenario = build(episode.scenario_key, seed=seed)
        kavach = Kavach(guard) if guard.enabled else None
        t = run_episode(scenario, episode.agent, RehearsalBackend(), episode.attack, kavach)
        writer.write(t)
        transcripts.append(t)

    console.print(
        "[yellow]REHEARSAL[/yellow] scripted agent, no model. "
        "Exercises the pipeline; the numbers are not findings.\n"
    )
    render(score(transcripts), f"rehearsal  policy={guard.name}  variant={variant}")
    console.print(f"\nruns/{run}")


@app.command()
def rescore(run: str = typer.Argument(..., help="Run directory under runs/.")) -> None:
    """Re-judge a recorded run without touching a model."""
    path = RUNS / run / "episodes.jsonl"
    if not path.exists():
        raise typer.BadParameter(f"no transcripts at {path}")
    transcripts = list(read_transcripts(path))
    render(score(transcripts), run)


@app.command()
def ablate(run: str = typer.Argument(..., help="Run directory under runs/.")) -> None:
    """Replay a recorded run through every policy. No model calls (D-021)."""
    path = RUNS / run / "episodes.jsonl"
    if not path.exists():
        raise typer.BadParameter(f"no transcripts at {path}")

    recorded = list(read_transcripts(path))
    policies = [Policy.off(), default_policy()] + [default_policy().without(d) for d in DEFENSES]
    matrix = replay_matrix(recorded, policies)

    table = Table(title=f"ablation from {len(recorded)} recordings", title_justify="left")
    table.add_column("policy")
    table.add_column("attack success", justify="right")
    table.add_column("benign utility", justify="right")
    table.add_column("blast radius / 1000", justify="right")
    table.add_column("exact", justify="right")

    for policy in policies:
        results = matrix[policy.name]
        card = score([r.transcript for r in results])
        fid = fidelity_summary(results)
        table.add_row(
            policy.name,
            f"{card.attack_success.value:.0%}",
            f"{card.benign_utility.value:.0%}",
            format_inr(card.blast_radius_paise_per_1000),
            f"{fid['exact']}/{len(results)}",
        )
    console.print(table)
    console.print(
        "\n[dim]Replay is a lower bound on attack success: a blocked call means no "
        "harm is recorded, while a real agent might have retried another way "
        "(D-050). Rows are exact only where nothing was blocked.[/dim]"
    )


@app.command()
def report(
    runs: list[str] = typer.Argument(..., help="One or more run directories."),
    out: str = typer.Option("report_out/scorecard.html", help="Where to write."),
) -> None:
    """Build the static HTML scorecard, with the ablation from the first run."""
    from pariksha.report.scorecard import Column, ablation_rows, render

    columns = []
    for name in runs:
        path = RUNS / name / "episodes.jsonl"
        if not path.exists():
            raise typer.BadParameter(f"no transcripts at {path}")
        columns.append(Column(name, score(list(read_transcripts(path)))))

    first = list(read_transcripts(RUNS / runs[0] / "episodes.jsonl"))
    policies = [Policy.off(), default_policy()] + [default_policy().without(d) for d in DEFENSES]
    matrix = replay_matrix(first, policies)
    scores = {p.name: score([r.transcript for r in matrix[p.name]]) for p in policies}

    html = render(
        columns,
        subtitle=f"{sum(c.card.episodes for c in columns)} episodes across "
        f"{len(columns)} run(s). Reproduce with pariksha bench.",
        ablation=ablation_rows(matrix, scores),
        footer="Pariksha. Every number regenerates from a single seed.",
    )
    target = Path(out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(html, encoding="utf-8")
    console.print(f"{target}  ({len(html):,} bytes)")


@app.command()
def cost(run: str = typer.Argument(..., help="Run directory under runs/.")) -> None:
    """Token usage for a recorded run."""
    path = RUNS / run / "episodes.jsonl"
    if not path.exists():
        raise typer.BadParameter(f"no transcripts at {path}")

    transcripts = list(read_transcripts(path))
    inp = sum(t.usage.input_tokens for t in transcripts)
    out = sum(t.usage.output_tokens for t in transcripts)
    cached = sum(t.usage.cache_read_tokens for t in transcripts)

    console.print(f"episodes      {len(transcripts)}")
    console.print(f"input tokens  {inp:,}" + (f"  ({cached:,} cached)" if cached else ""))
    console.print(f"output tokens {out:,}")
    console.print(f"per episode   {(inp + out) // max(len(transcripts), 1):,}")


@app.command()
def corpus() -> None:
    """Show what the benchmark covers."""
    from collections import Counter

    from pariksha.gym.attacks import ALL_ATTACKS, CATEGORIES

    episodes = build_grid()
    by_cat = Counter(a.category for a in ALL_ATTACKS)
    by_sub = Counter(a.subtlety for a in ALL_ATTACKS)

    table = Table(title="attack corpus", title_justify="left")
    table.add_column("category")
    table.add_column("attacks", justify="right")
    for c in CATEGORIES:
        table.add_row(c, str(by_cat[c]))
    console.print(table)
    console.print(
        f"\n{len(episodes)} episodes  |  {len(ALL_ATTACKS)} attacks  |  "
        f"blatant {by_sub[1]}, plausible {by_sub[2]}, subtle {by_sub[3]}"
    )


@app.command()
def policy(name: str = typer.Argument("default")) -> None:
    """Print a resolved policy."""
    p = make_policy(name)
    console.print(
        json.dumps(
            {
                "name": p.name,
                "enabled": sorted(p.enabled),
                "per_call_paise": p.per_call_paise,
                "aggregate_paise": p.aggregate_paise,
                "approval_threshold_paise": p.approval_threshold_paise,
                "require_trusted_destinations": p.require_trusted_destinations,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
