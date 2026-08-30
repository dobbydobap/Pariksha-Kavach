# Design decisions

Every non-obvious choice in Pariksha, with the reasoning. Code stays lean because
the reasoning lives here. Each entry is numbered so code comments and commit
messages can point at it (`see D-014`) instead of restating it.

Newest sections at the bottom. Nothing gets deleted; superseded decisions get a
**Superseded by D-nnn** line so the history of the thinking survives.

---

## Project

### D-001 — The project is a test harness, not another payment agent

Razorpay's Agent Studio already ships Dispute Auto-Responder, RTO Shield, RTO
Insights, Subscription Recovery, Abandoned Cart, Receivables, Cashflow
Forecaster, Settlement Insights and Bookkeeping agents. Their risk stack adds
Thirdwatch (acquired 2019, 300+ device and behavioural signals) and Bumblebee
(merchant risk review, 88% to 99%+). The buildathon's listed track "examples"
map almost one-to-one onto that shipped catalogue.

Building any listed example means demoing a nine-day version of a production
system to the team that built it. The requirements text underneath the examples
asks four separate times for measurement, bounds, audit trails and honest
exception lists. That describes a lab, not a product.

### D-002 — Submit under Track 05, Open Track

The work does not fit Tracks 1-4 honestly, and forcing it into one invites a
head-to-head comparison with a shipped Razorpay product. Open Track is
explicitly "build what you believe should exist" and is likely the thinnest
field.

### D-003 — Name: Pariksha, with the gateway called Kavach

Pariksha (परीक्षा) is "the examination". Kavach (कवच) is "armour". The pitch is
literally the name: Pariksha is the exam every money-moving agent should have to
pass; Kavach is the armour that lets it pass. Package layout `pariksha/kavach/`
reads correctly — the exam contains the armour.

### D-004 — Three axes, and the third one is rupees

Attack success rate alone is gameable: a gateway that blocks everything scores
perfectly and is useless. So utility is reported jointly with security, and the
frontier between them is the actual result.

The third axis, blast radius in rupees per 1,000 episodes, exists because
security is argued in percentages but budgeted in currency. It is the number a
payments executive can act on.

---

## Sandbox

### D-005 — Simulate Razorpay rather than use test mode as the primary target

Three reasons, in order of weight:

1. Razorpay test mode cannot create disputes, settlements or fraud. They can be
   fetched, not manufactured. Most of the interesting surface is unreachable.
2. A benchmark needs identical results across runs. Live APIs cannot give that.
3. Attacks must be planted in known fields so ground truth is exact.

Live test-mode passthrough still exists, as the conformance proof rather than
the measurement path.

### D-006 — The sandbox enforces exactly Razorpay's constraints, no more and no less

The load-bearing decision of the whole project.

It *does* reject a refund larger than the captured amount, because production
does. An attack relying on over-refunding a single payment would not work in
reality either, and the corpus must only contain attacks that would actually
land.

It *does not* reject `amount=500` when the agent meant Rs 500.00. That is a
legal partial refund of Rs 5.00 and production accepts it silently. Catching it
is Kavach's job, and Kavach is the thing under evaluation.

Erring either way breaks the benchmark: too strict measures the sandbox, too
loose measures attacks that cannot happen.

### D-007 — Amounts are integer paise, and floats are rejected at the type level

`rupees_to_paise` raises `TypeError` on a `float`. Binary floats cannot
represent 0.01 exactly, and silently losing a paise would undermine every number
reported. `Decimal` or `str` only.

### D-008 — Indian digit grouping is implemented by hand

`format(n, ',')` produces 3-3-3 grouping. Indian financial convention is 2-2-3
(lakh, crore). `Rs 1,00,00,000.00` is correct; `Rs 10,000,000.00` is not, and
using the wrong one in a submission to an Indian payments company is a tell.

### D-009 — Provenance is declared per field on the schema

Every entity field is marked `trusted` (Razorpay, a bank or a card network
produced it) or `untrusted` (an external human wrote it). Declaring it next to
the field means the taint tracker is driven by the model definition rather than
a separate list that drifts.

`provenance_of()` returns `untrusted` for unknown fields. This fails closed: a
field Razorpay adds later, or one we forget to annotate, is never silently
promoted to instruction-grade authority.

### D-010 — On an invoice, the amount is untrusted

Found by a failing test rather than by design. A payout agent reads a vendor
invoice, and on an invoice the *vendor* states what they are owed. Nothing about
that number is corroborated by Razorpay's records, unlike a refund which is
bounded by what was actually captured.

So `Invoice.amount` and every `InvoiceLineItem` field are untrusted, while
`fund_account_id` stays trusted because it comes from the merchant's own vendor
master. That asymmetry is the clearest single illustration of the taint model,
and the business-email-compromise attack tests exactly it.

### D-011 — Determinism comes from a single seed

All IDs come from a seeded RNG and all timestamps are offsets from a fixed epoch
(2026-08-01T00:00:00Z). One integer reproduces an entire run on any machine on
any date. Without this the numbers are anecdotes.

### D-012 — Errors are returned, not raised, at the tool boundary

`dispatch()` converts `RazorpayError` into a Razorpay-shaped error body. An HTTP
client would see a 400, not an exception, and how an agent recovers from a
realistic error is itself part of what gets scored.

---

## Tool surface

### D-013 — Tool descriptions state the paise unit explicitly

Every amount field says "Amount in PAISE, not rupees" with a worked example,
mirroring Razorpay's real documentation.

This makes the experiment harder on purpose. If the unit were omitted, a
paise/rupee error would be the harness's fault and the finding would be
worthless. Because the unit is stated plainly, a failure means the agent was
told and got it wrong anyway, under adversarial pressure. That is the result
worth reporting.

### D-014 — Strict schemas on every tool

`additionalProperties: false` plus explicit `required`, so `strict: true` can be
set API-side. A malformed call becomes unrepresentable, which separates "the
model emitted garbage" from "the model was manipulated into a valid but harmful
call". Only the second is interesting.

---

## Attack corpus

### D-015 — Attacks are separate from scenarios

A scenario is a believable slice of a merchant account containing no attack. An
attack is a payload plus a vector. Applying one to the other produces an
episode, so an adversarial run and its benign control differ in exactly one
variable. A test asserts the control stays byte-identical after injection.

### D-016 — Every payload targets a field marked untrusted

If an attack needed to write a trusted field it would not be prompt injection,
it would be a compromise of Razorpay itself, which is out of scope.

### D-017 — Ground truth is declarative, not a scripted call sequence

`Expectation` states bounds and prohibitions: a money ceiling, allowed
destinations, forbidden tools, PII markers, a call budget. Pinning an exact
expected tool sequence would fail agents that solve the task a different but
valid way, turning a safety benchmark into an instruction-following test.

### D-018 — Attacks carry a subtlety level

1 blatant, 2 plausible, 3 subtle. Results are reported per level because a
defense that only catches level 1 is not a defense. Anyone can filter an
obvious `=== SYSTEM NOTICE ===` block; the interesting question is level 3,
which reads as ordinary human prose.

### D-019 — Nine categories, four of which do not exist in generic benchmarks

AgentDojo and Agent Security Bench cover email, browsing and workspace agents.
No money, so no paise/rupee confusion, no refund replay, no destination
diversion, no RBI mandate breaches. Those four are where merchants actually lose
rupees, and the RBI category is derived from the Digital Payments E-Mandate
Framework of 21 April 2026 (AFA on registration and first debit, Rs 15,000
ceiling without AFA, 24-hour pre-debit notification, opt-out). A violation there
is a regulatory incident, not a bug.

---

## Measurement

### D-020 — Judges are deterministic code, never an LLM

Success criteria are assertions over the recorded tool-call stream and the
resulting money movements. Free, reproducible, and far harder to challenge in a
panel than "I asked a model whether the attack worked". Genuinely ambiguous
episodes go to a published exception list rather than to a model.

### D-021 — Ablation by offline replay, not by re-running agents

Each episode runs live once with guardrails off, recording the full tool-call
stream. Every guardrail configuration is then evaluated by replaying that
recording through the policy engine, costing nothing.

Reported honestly: replay is exact for terminal blocking defenses, and an upper
bound where a block would have changed the agent's later behaviour. A live
sample validates it and the agreement rate is published.

The constraint produced the method. It is the difference between a benchmark
nobody can afford to reproduce and one that runs from a single command.

---

## Models and cost

### D-022 — Hard constraint: zero marginal cost

Local inference was measured against the available hardware (i7-1355U, Intel
Iris Xe, 15.6 GB RAM, no discrete GPU). A 7B model on CPU puts a full run at
12-20 hours, which makes iteration impossible. Ruled out.

Anthropic free signup credits are the chosen backend. Roughly $5 of credit
against a Haiku 4.5 corpus cost of about $0.04 per episode leaves real headroom,
provided nothing is wasted.

### D-023 — A mock backend, and the entire pipeline is built against it

A deterministic backend that emits scripted tool calls. Runner, judges, scoring,
gateway, replay and report are all developed and tested against it at zero cost.
Credits are spent only on final measured runs.

This is not only a budget measure. It makes the harness testable in CI without
any key at all, which is what lets a judge clone the repo and verify the
machinery independently of the model results.

### D-024 — The model backend is a swappable interface

`gym/backends/` defines a protocol; `mock` and `anthropic` implement it. Adding
Groq or Gemini is a single file. A benchmark hard-wired to one vendor is a
design flaw, and the model is properly a parameter of the experiment rather than
a dependency of the harness.

### D-025 — Prompt caching is mandatory and its absence is a hard failure

The system prompt and tool definitions are byte-identical across every episode,
so cache hit rate should approach 100% on the prefix. The runner asserts
`cache_read_input_tokens > 0` and aborts loudly if it is zero. A silent cache
miss is the most likely way a fixed credit budget disappears.

### D-026 — Haiku 4.5 is the workhorse; Claude models are the target of interest

Razorpay's Agent Studio runs on Claude, so Claude numbers are the ones that
speak to this panel. Haiku 4.5 carries the full corpus; larger models run on
subsets as credits allow. "Cheaper models are measurably more injectable" is a
real finding, so the model sweep is a result rather than a cost dodge.

---

## Engineering

### D-027 — Kavach is an MCP proxy, not a library

A library only protects agents that import it. As a proxy in front of the MCP
endpoint Razorpay already ships (`mcp.razorpay.com/mcp`, 50+ tools), any agent
from any developer in any framework is protected with no code change.

This is the answer to every generality question, and it is what makes the work
deployable in front of a marketplace rather than a self-contained project.

### D-028 — Python 3.12, not 3.14

3.14 is installed locally but wheel coverage is still patchy. Judges will clone
this repo, and install friction is a self-inflicted wound.

### D-029 — Agents run on the Client SDK Tool Runner, not the Claude Agent SDK

The Agent SDK ships Claude Code's full system prompt plus Read/Write/Edit/Bash/
WebSearch, none of which a payment agent uses. That is wasted spend on every
turn and, worse, experimental noise: it would measure Claude Code's harness
rather than the agent.

One agent is additionally implemented on the Agent SDK as a compatibility proof,
since Agent Studio is built on it, demonstrating the gateway protects an
Agent-SDK agent unchanged.

Note: Anthropic explicitly disallows claude.ai subscription auth for
SDK-built agents, so API-key auth is the only option.

### D-030 — Rationale lives here, not in the code

Code carries short functional docstrings and comments only where behaviour is
genuinely surprising. Long explanatory prose in source files goes stale, bloats
diffs and buries the logic. This file is the single place reasoning is recorded,
and code references it by decision number.
