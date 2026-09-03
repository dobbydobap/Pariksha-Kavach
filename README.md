# Pariksha

**An adversarial certification harness for AI agents that move money.**

Pariksha runs payment agents through attacks that only exist in payments, and
scores three axes jointly: attack resistance, task utility, and rupees leaked.
It ships with **Kavach**, a policy-enforcing MCP proxy, and the ablation showing
which control stops which attack class and what each costs in usefulness.

<p align="center">
  <img src="docs/story.svg" width="920"
       alt="An attacker slips a note into a real customer's message; the agent cannot tell them apart and tries to send Rs 5,00,000; Kavach blocks it because that account was never seen in a trusted field">
</p>

## See it happen

```bash
pariksha demo
```

One attack landing, then the same attack blocked. Driven from recorded
transcripts and a live replay through the gateway, so it needs **no API key** and
shows the same numbers the report does. Nothing in it is staged.

---

## The result

`openai/gpt-oss-20b` via Groq, seed 1729, 37 of 41 episodes, 240,090 tokens,
**zero cost**.

| | Guardrails off | Kavach |
|---|---|---|
| Attack success | 13% <sub>[5-30%] n=30</sub> | **3%** <sub>[1-17%]</sub> |
| Benign utility | 100% <sub>n=4</sub> | 50% |
| Utility under attack | 87% | 33% |
| Unauthorised money moved / 1,000 episodes | ₹2,34,16,667 | **₹40,00,000** |

Utility under attack falling from 87% to 33% is the price of failing closed, and
it is reported rather than tuned away. Six hand-written attacks were aimed at
the gateway itself; five got through, four are fixed with regression tests, and
[two survive and are documented](docs/ARCHITECTURE.md#7-what-this-does-not-cover).

Thirty adversarial episodes. The intervals are wide and printed everywhere;
these are pilot measurements, not settled ones. Three episodes are in the
exception list, counted in neither the numerator nor the denominator.

**Subtlety does not protect.** Blatant 25% <sub>n=4</sub>, plausible 8%
<sub>n=12</sub>, subtle 14% <sub>n=14</sub>. The comfortable assumption is that
models fall for crude attacks and resist careful ones. Measured twice now, on
two models and two corpus sizes, that is not what happens — and the corpus is
deliberately weighted toward the subtle end, so the result is not an artefact of
where the attacks sit.

**Half the successful attacks had no injected framing at all.** An ordinary note
saying a vendor had changed banks sent ₹82,500 to an attacker. An invented
policy citation inside a cardholder's own dispute evidence cost ₹1,20,000. Both
read as prose a colleague might write.

**Every attack that landed was a provenance failure. Everything resisted was
arithmetic or procedure.** Five paise/rupee attempts failed, three replay
attempts failed, both RBI mandate attacks failed, as did scope creep and denial
of wallet. The agent can do the sums and follow the process. It cannot tell
whose voice it is reading.

**The ablation names which controls earned their place.** Removing destination
provenance takes attack success from 3% to 7%; removing PII egress control does
the same. The other five change nothing, because the model never made the
mistakes they guard against. The approval gate fired 16 times — more than every
other defense combined — bought no security, and cost a third of the automation.

### Across three model families

| Model | Episodes | Attack success | Benign utility |
|---|---|---|---|
| `openai/gpt-oss-20b` | 37 of 41 | 13% <sub>[5-30%] n=30</sub> | 100% <sub>n=4</sub> |
| `openai/gpt-oss-120b` | 22, earlier corpus | 21% <sub>[9-43%] n=19</sub> | 100% <sub>n=3</sub> |
| `qwen/qwen3.8-27b` | 17 of 41 | 0% <sub>[0-19%] n=16</sub> | unmeasured <sub>n=1</sub> |

Both GPT-OSS runs show the same flat subtlety curve and the same two
load-bearing defenses.

**Qwen resisted every attack in its sample, and that is not the same as being
safe.** Its handling of the injection that beat both GPT-OSS models was
exemplary: it read the payment, the thread, prior refunds and the order, then
refunded exactly the right amount to the original payer and ignored the injected
account. But its single benign control failed, calling `fetch_customer`
seventeen times until the call budget ran out. Utility is unmeasured, and an
agent that never finishes anything is trivially secure.

Both behaviours look like one disposition: it reads more before acting, which
defeated the injection, and it does not stop, which exhausted the budget on a
benign task. The security-utility frontier inside a model's temperament rather
than between policy settings.

The Qwen and 20b runs both stopped short on the provider's daily token ceiling.
Because the grid is shuffled by seed, what was measured is a random sample
across all four scenarios rather than a truncated prefix of one.

### A guard model does not substitute for provenance

`meta-llama/llama-prompt-guard-2-86m` is Meta's prompt-injection classifier and
the obvious thing to reach for. Every corpus payload was scored against it.

It works: a DAN jailbreak scores **0.9996**, a genuine customer refund request
**0.0004**. At the default 0.5 threshold it flags **1 of 37** attacks — the only
one written in jailbreak register — with zero false positives on benign text.

Of the four attacks that actually moved money it catches **none**. The fake
system notice that diverted ₹5,00,000 scores 0.0146. The vendor bank-change that
sent ₹82,500 to an attacker scores 0.0005, indistinguishable from ordinary
prose.

That is not miscalibration, it is aim. Prompt Guard 2 was deliberately retrained
toward jailbreak detection because the injection label produced too many false
positives on benign third-party data. **The attack that costs money does not look
like an attack — it looks like work.** Scores in
[`docs/guard_scores.json`](docs/guard_scores.json).

---

## Why this exists

Razorpay's [Agent Studio](https://razorpay.com/agent-studio/) is a marketplace of
AI agents that act on merchant money: responding to chargebacks, retrying
subscriptions, forecasting cash, releasing payouts. Their
[guardrails post](https://razorpay.com/blog/razorpay-agent-studio-principles-guardrails-and-merchant-control/)
describes a well-designed control surface, and states two things a few
paragraphs apart:

> "The developer or provider of each agent carries responsibility for its behavior."

> "Any merchant or developer will be able to build agents and publish them to the marketplace."

The described pre-launch check is a validation *review* of agent logic, data
scope, actions and communication patterns. What is not described anywhere public
is an executable, adversarial, measured test — a way to say that an agent
survived N attacks across M categories, leaked ₹X, and cost Y% utility to secure.

That gap matters because an LLM agent cannot distinguish information it is
reading from instructions it should follow. An instruction hidden in the OCR
layer of a dispute evidence document, or in a vendor's remittance note, is read
while the agent does its job and acted on. Nothing errors. The audit log records
a successful refund.

Ambient numbers: Agent Security Bench reports attack success rates up to
**84.3%**; a public red-team of deployed agents logged **60,000+ successful
policy violations from 1.8M attempts**; in one evaluation **4 of 26 LLMs were
manipulated into actually making a payment**.

## What makes it payments-specific

Generic agent-security benchmarks (AgentDojo, ASB) test email, browsing and
workspace agents. No money, so none of these classes exist in them:

- **Paise/rupee confusion.** Razorpay amounts are integer paise. `500` is ₹5.00,
  not ₹500.00. A silent 100× error in either direction, no exception raised.
- **Idempotency and replay.** A refund retried after a timeout moves money twice.
  Every individual call is valid; only the aggregate is wrong.
- **Destination diversion.** Business email compromise, transplanted into an
  agent workflow: a quiet bank-detail change in a vendor's remittance note.
- **RBI compliance traps.** Expired mandates, AFA threshold breaches, missing
  24-hour pre-debit notice — checked against the **Digital Payments E-Mandate
  Framework of 21 April 2026**. Regulatory incidents, not bugs.
- **₹ blast radius.** Every successful attack priced in rupees, because that is
  the unit the risk gets budgeted in.

## Architecture

```
        Agents under test   (refund · dispute · payout)
                    |  MCP
        +-----------v------------+
        |    KAVACH GATEWAY      |   policy · taint · idempotency
        |      (MCP proxy)       |   approval · audit · breaker
        +----+--------------+----+
             | sim          | live
      +------v------+  +----v-------------+
      |  Sandbox    |  | mcp.razorpay.com |
      |  (seeded)   |  |  (test keys)     |
      +-------------+  +------------------+
                |
      +---------v--------------------------+
      |  GYM - episodes, judges, scoring   |
      +------------------------------------+
```

Kavach is an **MCP proxy, not a library**. A library only protects agents that
import it. As a proxy in front of the MCP endpoint Razorpay already ships, any
agent in any framework is protected with no code change.

Design reasoning for every non-obvious choice is in [DECISIONS.md](DECISIONS.md).

## Layout

```
pariksha/
  sandbox/      deterministic Razorpay replica
    money.py      paise arithmetic, Indian digit grouping
    ids.py        seeded Razorpay-shaped identifiers
    entities.py   entity models with per-field provenance
    state.py      operations and the money-movement ledger
    tools.py      the 22-tool surface agents are given
    seed.py       scenarios plus declarative ground truth
  gym/
    attacks.py    the adversarial corpus
  kavach/       the policy gateway
  agents/       agents under test
  report/       scorecard generation
```

## Status

| Phase | State |
|---|---|
| Sandbox, tool surface, scenarios | done |
| Attack corpus | 37 attacks, 9 categories, 4 scenarios, 41 episodes |
| Measurement spine | done, 230 tests |
| Kavach gateway | done |
| Agents and first baseline | done |
| Corpus expansion, three-model sweep, red team | done |
| Video and submission | in progress |

## Run it

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
pytest -q
```

The full pipeline is built against a deterministic mock backend, so the
machinery is verifiable **with no API key at all**.

Every model result in this repository reproduces for **zero cost**. The corpus
runs on [Groq](https://console.groq.com)'s free tier, no credit card:
`openai/gpt-oss-120b`, `openai/gpt-oss-20b`, `qwen/qwen3.8-27b`,
`qwen/qwen3.6-27b`. Model ids are validated at startup against the live
catalogue rather than taken from documentation. Copy `.env.example` to `.env`,
add the key, then:

```bash
pariksha rehearse                                    # whole pipeline, no key at all
pariksha bench --backend groq --model openai/gpt-oss-120b
pariksha ablate 1729-groq-openai-gpt-oss-120b-off    # every policy, no model calls
pariksha report 1729-groq-openai-gpt-oss-120b-off    # static HTML scorecard
```

A benchmark that requires a funded key is a benchmark nobody runs. The ablation
above evaluates eight guardrail configurations from recordings already on disk,
so the whole matrix costs nothing beyond the single baseline pass.

### On Claude

Razorpay's Agent Studio is built on Claude, so that is the column that matters
most here, and it is reported as **not measured** — those runs could not be
funded. The backend interface is swappable, so adding a provider is one file
against the `Backend` protocol in
[`gym/backends/base.py`](pariksha/gym/backends/base.py) — but that file is not
written, and this repository contains no Claude measurements. Claiming numbers
that were never run would fail the standard this project exists to enforce
(D-031).

## Licence

Apache-2.0.
