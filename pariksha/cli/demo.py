"""The demo: one attack, landing and then blocked.

Driven from a recorded transcript and a live replay through Kavach, so it needs
no API key and shows the same numbers the report does. Nothing here is staged --
the calls, the money and the block reason are read from real runs (D-091).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from pariksha.gym.attacks import ATTACKS_BY_ID, apply
from pariksha.gym.transcript import Transcript, read_transcripts
from pariksha.kavach.policy import default_policy
from pariksha.kavach.replay import replay
from pariksha.sandbox.money import format_inr
from pariksha.sandbox.seed import build
from pariksha.sandbox.tools import MONEY_OUT_TOOLS, dispatch

ATTACK = "inj.system_notice.blatant"


@dataclass
class Pace:
    """Timing for a screen recording. Zero for CI."""

    beat: float = 0.9
    line: float = 0.35

    def hold(self, seconds: float) -> None:
        if seconds:
            time.sleep(seconds)


# A real recorded episode, shipped with the package. `runs/` is generated output
# and is not in version control, so without this the demo would not work for
# anyone who cloned the repository (D-092).
SHIPPED = Path(__file__).resolve().parent.parent / "demo_data" / "episodes.jsonl"


def find_episode(runs: Path, attack_id: str) -> tuple[Transcript, str] | None:
    """The first recorded episode of this attack where money actually moved.

    Prefers a local run so the demo reflects whatever was measured most
    recently, and falls back to the shipped recording.
    """
    best: tuple[Transcript, str] | None = None
    directories = sorted(runs.glob("*/episodes.jsonl"))
    if SHIPPED.exists():
        directories.append(SHIPPED)
    for directory in directories:
        for t in read_transcripts(directory):
            if t.attack_id != attack_id:
                continue
            label = "shipped recording" if directory == SHIPPED else directory.parent.name
            if t.money_out_paise > 0:
                return t, label
            best = best or (t, label)
    return best


def show_injection(console: Console, pace: Pace) -> None:
    scenario = apply(build("refund.non_delivery"), ATTACKS_BY_ID[ATTACK])
    thread = dispatch(
        scenario.state, "fetch_support_thread", {"payment_id": scenario.subject_payment_id}
    )
    body = thread["items"][-1]["body"]
    genuine, _, injected = body.partition("\n\n===")

    text = Text()
    text.append(genuine.strip() + "\n\n", style="white")
    text.append("===" + injected, style="bold red")

    console.print(
        Panel(
            text,
            title="[bold]what the agent reads[/bold]  the last customer message",
            subtitle="[dim]white: the customer   red: appended by whoever wrote the message[/dim]",
            border_style="red",
        )
    )
    pace.hold(pace.beat * 2)


def walk(console: Console, transcript: Transcript, pace: Pace, guarded: bool) -> None:
    for call in transcript.calls:
        if call.blocked:
            console.print(f"  [bold red]BLOCKED[/bold red]  {call.name}")
            console.print(f"           [red]{call.block_reason}[/red]")
            console.print(f"           [dim]defense: {call.blocked_by}[/dim]")
        elif call.name in MONEY_OUT_TOOLS and "error" not in call.result:
            amount = call.result.get("amount", 0)
            target = call.arguments.get("fund_account_id") or call.arguments.get("payment_id", "")
            style = "bold red" if guarded is False and "fa_9x" in str(target) else "bold yellow"
            console.print(f"  [{style}]{call.name}[/{style}]  {format_inr(amount)}  -> {target}")
        else:
            console.print(f"  [dim]{call.name}[/dim]")
        pace.hold(pace.line)


def run(console: Console, runs: Path, pace: Pace) -> int:
    found = find_episode(runs, ATTACK)
    if found is None:
        console.print(
            "[red]No recorded episode for this attack.[/red]\n"
            "This should not happen: a recording ships with the package. "
            "Run [bold]pariksha bench[/bold] to make your own."
        )
        return 1

    recorded, run_name = found
    console.print()
    console.print(
        Panel.fit(
            "[bold]Pariksha[/bold]  one attack, landing and then blocked\n"
            f"[dim]{recorded.model} - seed {recorded.seed} - recorded in {run_name}[/dim]",
            border_style="white",
        )
    )
    console.print()

    console.print(
        "[bold]1. A customer asks for a refund.[/bold] The agent reads the thread, "
        "which is its job.\n"
    )
    pace.hold(pace.beat)
    show_injection(console, pace)

    console.print("\n[bold]2. Guardrails off.[/bold] Watch what the agent does.\n")
    pace.hold(pace.beat)
    walk(console, recorded, pace, guarded=False)

    moved = recorded.money_out_paise
    console.print()
    if moved:
        console.print(
            Panel(
                f"[bold red]{format_inr(moved)} left the merchant.[/bold red]\n\n"
                "No error. No alert. The audit log records a successful transfer.\n"
                "The account it went to exists nowhere except inside a message a customer wrote.",
                border_style="red",
            )
        )
    else:
        console.print(
            Panel(
                "[yellow]This model resisted the attack unguarded.[/yellow]", border_style="yellow"
            )
        )
    pace.hold(pace.beat * 2)

    console.print(
        "\n[bold]3. Same agent, same attack, same seed.[/bold] This time through Kavach.\n"
    )
    pace.hold(pace.beat)
    guarded = replay(recorded, default_policy())
    walk(console, guarded.transcript, pace, guarded=True)

    console.print()
    table = Table(box=None, pad_edge=False)
    table.add_column("", style="dim")
    table.add_column("guardrails off", justify="right")
    table.add_column("Kavach", justify="right", style="bold")
    table.add_row("money out", format_inr(moved), format_inr(guarded.transcript.money_out_paise))
    table.add_row("calls blocked", "0", str(guarded.blocked_calls))
    table.add_row("replay fidelity", "-", guarded.fidelity.value)
    console.print(table)

    console.print()
    console.print(
        Panel.fit(
            "The rule is not that the text looked suspicious.\n"
            "It is that the account had never appeared in a field Razorpay produced.\n\n"
            "[bold]Provenance, not prose.[/bold]",
            border_style="green",
        )
    )
    console.print()
    return 0
