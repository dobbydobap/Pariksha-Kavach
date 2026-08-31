"""Static HTML scorecard.

Self-contained: no CDN, no fonts, no scripts. A report that needs the network
to render is a report that stops rendering.

Every rate is printed with its Wilson interval and its sample size, because the
headline percentage on its own overstates what a corpus of this size measured
(D-004).
"""

from __future__ import annotations

from dataclasses import dataclass

from jinja2 import Environment

from pariksha.gym.score import Scorecard
from pariksha.sandbox.money import format_inr

SUBTLETY = {1: "blatant", 2: "plausible", 3: "subtle"}

CSS = """
:root { --fg:#1a1a1a; --dim:#666; --line:#e2e2e2; --bad:#b3261e; --ok:#1b6b3a; --bg:#fff; }
* { box-sizing:border-box; }
body { margin:0; padding:2.5rem 1.5rem; background:var(--bg); color:var(--fg);
  font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif; }
main { max-width:60rem; margin:0 auto; }
h1 { font-size:1.6rem; margin:0 0 .25rem; letter-spacing:-.01em; }
h2 { font-size:1.05rem; margin:2.5rem 0 .75rem; font-weight:600; }
p.sub { color:var(--dim); margin:0 0 2rem; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th,td { text-align:left; padding:.5rem .6rem; border-bottom:1px solid var(--line); }
th { font-weight:600; font-size:.82rem; color:var(--dim); text-transform:uppercase;
  letter-spacing:.04em; }
td.n, th.n { text-align:right; }
.ci { color:var(--dim); font-size:.85em; }
.bad { color:var(--bad); font-weight:600; }
.ok { color:var(--ok); font-weight:600; }
.note { color:var(--dim); font-size:.88rem; margin-top:.6rem; }
.scroll { overflow-x:auto; }
.bar { display:inline-block; height:.55rem; background:var(--bad); border-radius:1px;
  vertical-align:middle; margin-right:.4rem; min-width:1px; }
footer { margin-top:3rem; padding-top:1rem; border-top:1px solid var(--line);
  color:var(--dim); font-size:.85rem; }
"""

TEMPLATE = """<!doctype html>
<meta charset="utf-8">
<title>{{ title }}</title>
<style>{{ css }}</style>
<main>
<h1>{{ title }}</h1>
<p class="sub">{{ subtitle }}</p>

<h2>Headline</h2>
<div class="scroll"><table>
<tr><th>Metric</th>{% for c in columns %}<th class="n">{{ c.label }}</th>{% endfor %}</tr>
{% for row in headline %}
<tr><td>{{ row.name }}</td>
{% for cell in row.cells %}<td class="n">{{ cell }}</td>{% endfor %}</tr>
{% endfor %}
</table></div>
<p class="note">Rates carry 95% Wilson intervals and sample sizes. Blast radius is
unauthorised money movement per 1,000 attacked episodes.</p>

<h2>Attack success by category</h2>
<div class="scroll"><table>
<tr><th>Category</th>{% for c in columns %}<th class="n">{{ c.label }}</th>{% endfor %}</tr>
{% for row in categories %}
<tr><td>{{ row.name }}</td>
{% for cell in row.cells %}<td class="n">{{ cell }}</td>{% endfor %}</tr>
{% endfor %}
</table></div>

<h2>Attack success by subtlety</h2>
<div class="scroll"><table>
<tr><th>Level</th>{% for c in columns %}<th class="n">{{ c.label }}</th>{% endfor %}</tr>
{% for row in subtlety %}
<tr><td>{{ row.name }}</td>
{% for cell in row.cells %}<td class="n">{{ cell }}</td>{% endfor %}</tr>
{% endfor %}
</table></div>
<p class="note">A defense that only stops blatant attacks is not a defense. Level 3
reads as ordinary human prose with no injected framing.</p>

{% if ablation %}
<h2>Ablation</h2>
<div class="scroll"><table>
<tr><th>Policy</th><th class="n">Attack success</th><th class="n">Benign utility</th>
<th class="n">Blast radius / 1000</th><th class="n">Exact</th></tr>
{% for row in ablation %}
<tr><td>{{ row.policy }}</td>
<td class="n"><span class="bar" style="width:{{ row.bar }}px"></span>{{ row.attack }}</td>
<td class="n">{{ row.utility }}</td><td class="n">{{ row.blast }}</td>
<td class="n">{{ row.exact }}</td></tr>
{% endfor %}
</table></div>
<p class="note">Computed by replaying recordings through each policy, not by
re-running agents. Replay is a <em>lower bound</em> on attack success: a blocked
call means no harm is recorded, while a real agent might have retried another
way. Rows are exact only where nothing was blocked.</p>
{% endif %}

{% if exceptions %}
<h2>Exception list</h2>
<div class="scroll"><table>
<tr><th>Episode</th><th>Why it could not be judged</th></tr>
{% for e in exceptions %}
<tr><td>{{ e.episode }}</td><td>{{ e.reason }}</td></tr>
{% endfor %}
</table></div>
<p class="note">These episodes are in neither the numerator nor the denominator of
any rate above. Counting them either way would misreport.</p>
{% endif %}

<footer>{{ footer }}</footer>
</main>
"""


@dataclass
class Column:
    label: str
    card: Scorecard


def _rate(card: Scorecard, get) -> str:
    r = get(card)
    if r.total == 0:
        return "n/a"
    lo, hi = r.interval
    return f"{r.value:.0%} <span class='ci'>[{lo:.0%}-{hi:.0%}] n={r.total}</span>"


def render(
    columns: list[Column],
    title: str = "Pariksha scorecard",
    subtitle: str = "",
    ablation: list[dict] | None = None,
    footer: str = "",
) -> str:
    """Build the HTML report. Markup is trusted; only data is escaped."""
    env = Environment(autoescape=False)

    headline = [
        {
            "name": name,
            "cells": [fn(c.card) for c in columns],
        }
        for name, fn in [
            ("Episodes", lambda c: str(c.episodes)),
            ("Attack success", lambda c: _rate(c, lambda x: x.attack_success)),
            ("Any violation", lambda c: _rate(c, lambda x: x.any_violation)),
            ("Benign utility", lambda c: _rate(c, lambda x: x.benign_utility)),
            ("Utility under attack", lambda c: _rate(c, lambda x: x.attacked_utility)),
            ("Escalated to a human", lambda c: _rate(c, lambda x: x.escalation)),
            (
                "Blast radius / 1000",
                lambda c: format_inr(c.blast_radius_paise_per_1000),
            ),
            ("Undetermined", lambda c: str(c.undetermined)),
        ]
    ]

    names = sorted({k for c in columns for k in c.card.by_category})
    categories = [
        {
            "name": name,
            "cells": [
                _rate(c.card, lambda x, n=name: x.by_category.get(n))
                if name in c.card.by_category
                else "n/a"
                for c in columns
            ],
        }
        for name in names
    ]

    levels = sorted({k for c in columns for k in c.card.by_subtlety})
    subtlety = [
        {
            "name": f"{level} - {SUBTLETY.get(level, '')}",
            "cells": [
                _rate(c.card, lambda x, level=level: x.by_subtlety.get(level))
                if level in c.card.by_subtlety
                else "n/a"
                for c in columns
            ],
        }
        for level in levels
    ]

    exceptions = [
        {"episode": e.attack_id or "benign", "reason": e.reason}
        for c in columns
        for e in c.card.exceptions
    ]

    return env.from_string(TEMPLATE).render(
        title=title,
        subtitle=subtitle,
        css=CSS,
        columns=columns,
        headline=headline,
        categories=categories,
        subtlety=subtlety,
        ablation=ablation or [],
        exceptions=exceptions,
        footer=footer,
    )


def ablation_rows(matrix, scores) -> list[dict]:
    """Rows for the ablation table, widest bar at the highest attack success."""
    peak = max((s.attack_success.value for s in scores.values()), default=0) or 1
    rows = []
    for name, card in scores.items():
        results = matrix[name]
        exact = sum(1 for r in results if r.is_exact)
        rows.append(
            {
                "policy": name,
                "attack": f"{card.attack_success.value:.0%}",
                "utility": f"{card.benign_utility.value:.0%}",
                "blast": format_inr(card.blast_radius_paise_per_1000),
                "exact": f"{exact}/{len(results)}",
                "bar": round(card.attack_success.value / peak * 90),
            }
        )
    return rows
