# Pariksha

**An adversarial certification harness for AI agents that move money.**

Pariksha runs payment agents through attacks that only exist in payments, and
scores three axes jointly: attack resistance, task utility, and rupees leaked.
It ships with **Kavach**, a policy-enforcing MCP proxy, and the ablation showing
which control stops which attack class and what each costs in usefulness.

> In development. Every `TBD` below is a number this harness produces. None of
> them are claims being made in advance.

---

## The result

| | Guardrails off | Kavach on |
|---|---|---|
| Attack success rate | `TBD` | `TBD` |
| Benign task utility | `TBD` | `TBD` |
| Unauthorised money moved, per 1,000 episodes | `TBD` | `TBD` |

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
    tools.py      the 19-tool surface agents are given
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
| Attack corpus | 19 attacks, 9 categories, 3 subtlety levels |
| Measurement spine | in progress |
| Kavach gateway | not started |
| Agents and baseline run | not started |

Task board: [TASKS.md](TASKS.md).

## Run it

```bash
uv venv --python 3.12
uv pip install -e ".[dev]"
pytest -q
```

The full pipeline is built against a deterministic mock backend, so the
machinery is verifiable **without any API key**. A key is needed only to
reproduce the model results.

## Licence

Apache-2.0.
