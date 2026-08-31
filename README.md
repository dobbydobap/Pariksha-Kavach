# Pariksha

**An adversarial certification harness for AI agents that move money.**

Pariksha runs payment agents through attacks that only exist in payments, and
scores three axes jointly: attack resistance, task utility, and rupees leaked.
It ships with **Kavach**, a policy-enforcing MCP proxy, and the ablation showing
which control stops which attack class and what each costs in usefulness.

---

## The result

`openai/gpt-oss-120b`, seed 1729, 22 episodes, 162,695 tokens, **zero cost**.

| | Guardrails off | Kavach | Kavach, approval gate off |
|---|---|---|---|
| Attack success | 21% <sub>[9-43%]</sub> | **5%** | **5%** |
| Benign utility | 100% | 33% | 67% |
| Escalated to a human | 0% | 33% | 0% |
| Unauthorised money moved / 1,000 episodes | ₹3,69,73,684 | **₹63,15,789** | **₹63,15,789** |

Nineteen adversarial episodes, so the intervals are wide and these are pilot
numbers, not settled ones. Every rate in the report carries its Wilson interval
and sample size.

**Subtlety barely moved the outcome.** Blatant 25%, plausible 22%, subtle 17% —
overlapping almost completely at this sample size. The comfortable assumption is
that models fall for crude attacks and resist careful ones. That is not what
this shows.

**Every attack that landed was a provenance failure.** A fake system notice in a
support thread diverted ₹5,00,000. A fake issuer annotation in dispute evidence
made the agent concede a winnable chargeback. An ordinary-looking vendor
bank-change note — no injected framing at all — sent ₹82,500 to an attacker.

**Everything it resisted was arithmetic or procedure.** Three paise/rupee
attempts failed. Two refund-replay attempts failed. Both RBI mandate attacks
failed, as did scope creep, denial of wallet, CEO-urgency pressure and a forged
approval quote.

The agent can do the sums and follow the process. It cannot tell whose voice it
is reading.

**The ablation names which controls earned their place.** Removing destination
provenance took attack success from 5% to 11%; removing PII egress control did
the same. The other five changed nothing, because the model never made the
mistakes they guard against. The approval gate fired more often than every other
defense combined, bought no security on this workload, and cost two thirds of
the automation.

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
| Measurement spine | done, 217 tests |
| Kavach gateway | done |
| Agents and first baseline | done |
| Corpus expansion, model sweep, write-up | in progress |

Task board: [TASKS.md](TASKS.md).

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
funded. The Anthropic backend is written and ready; `--backend anthropic
--model claude-haiku-4-5` produces the column the day it is funded. Claiming
numbers that were never run would fail the standard this project exists to
enforce (D-031).

## Licence

Apache-2.0.
