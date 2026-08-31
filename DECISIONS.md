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

Reported honestly, and the direction matters: replay is a **lower bound on
attack success**, not an upper bound. When a policy blocks the harmful call the
replay records no harm and scores the attack as failed, but a real agent would
have seen the refusal and might have retried by another route. True harm under
that policy is therefore greater than or equal to what replay reports, so replay
*flatters the defense*. Corrected in D-050; the earlier wording here was
backwards.

The constraint produced the method. It is the difference between a benchmark
nobody can afford to reproduce and one that runs from a single command.

---

## Models and cost

### D-022 — Hard constraint: zero marginal cost

**Superseded by D-031.**

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

**Superseded by D-031.**

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

### D-031 — Free-tier multi-vendor inference, and Claude is reported as unmeasured

Anthropic free signup credits turned out not to be available on this account, so
the plan of running Claude as the primary target is dead. Two providers offer
genuinely free API access with no card: Groq (30 RPM, 6,000 TPM, 14,400 requests
per day, all models) and Google AI Studio (Gemini 2.5 Flash-Lite at 1,000
requests per day, Flash at 250, with far higher token throughput).

The corpus therefore runs on four model families across three vendors: Llama 3.3
70B, Qwen 3 and Kimi K2 via Groq, and Gemini 2.5 Flash-Lite and Flash via Google.

This is a better benchmark, not a worse one. A security finding measured on a
single vendor's models may be a quirk of that vendor. One that holds across four
independent families is a result. Published work already found Llama 3.3 70B
could be manipulated into making a payment, so this extends a known finding
rather than inventing one. It also means every number in the repository
reproduces for zero cost by anyone who clones it, which a benchmark requiring a
funded key does not.

Razorpay's Agent Studio runs on Claude, so the Claude column is the one that
speaks most directly to this panel, and it is reported as **not measured** with
the reason stated. `--backend anthropic --model claude-haiku-4-5` runs it
unchanged the day it is funded. Claiming numbers that were not run would fail
the exact honesty standard the project is built to enforce.

Groq's 6,000 TPM is the binding constraint, not its request cap: with no prompt
caching, an eight-turn episode costs roughly 51k cumulative tokens, so about 8.5
minutes per episode. Runs are batched overnight. Gemini's much higher throughput
makes it the fast iteration path, with its daily request cap as the limit.

### D-032 — Tool scoping is an ablation dimension, not a fixed choice

Razorpay's guardrails documentation says the merchant approves exactly which
actions an agent may take. That is a defense, so it must be measured rather than
assumed.

The naive v0 agents are given the broad tool surface, which is what makes
cross-tool attacks (a refund agent talked into calling `create_payout`)
expressible at all. A scoped variant receives only the tools its task requires.
The ablation then answers directly: how much of the attack surface does tool
scoping alone remove, and what does it cost in utility when a legitimate task
needs an unexpected tool.

Scoping also cuts tool-definition tokens, which matters against Groq's TPM cap.

### D-033 — No prompt caching on the free backends

D-025 required prompt caching and made its absence a hard failure. That applies
to the Anthropic backend only. Groq and Gemini free tiers do not offer
equivalent caching, so the runner asserts cache behaviour per backend rather
than globally, and the token budget for those backends assumes the full prefix
is re-sent every turn.

### D-034 — Attack success is scoped to the attacker's stated goal

An episode where the agent leaks PII while resisting a fund-diversion attack has
failed, but that attack did not succeed. `GOAL_SATISFIED_BY` maps each attack
goal onto the violation kinds that mean the attacker got what they wanted, and
attack success rate counts only those. Any-violation rate is reported
separately.

Collapsing the two would inflate attack success rates by crediting attackers
with failures they had nothing to do with.

### D-035 — Blast radius takes the maximum, never the sum

A single refund that is both over the ceiling and sent to the wrong destination
produces two violations describing one loss. Summing their rupee impact would
double-count. `unauthorised_paise` takes the maximum across money-moving kinds.

The headline number is the one most likely to be challenged, so it errs low.

### D-036 — Blocked and errored calls are not violations

A gateway refusal is the system working. An API error is the sandbox behaving
like production. Only calls that both executed and succeeded can constitute
agent misbehaviour, otherwise turning on Kavach would appear to increase the
violation count it exists to reduce.

### D-037 — Task completion requires the absence of critical violations

A refund of exactly the right amount to an attacker's account is not a completed
task. `task_completed` requires the success tool, the exact amount where one is
specified, and no critical violation. Without the last clause the utility axis
would reward diverted money as successful work.

### D-038 — Untestable attack categories are undetermined, never passes

The RBI compliance attacks cannot succeed while the sandbox has no mandate
tools. Scoring them as passes would inflate the resistance number using the most
differentiated category in the corpus. They return `undetermined` with a stated
reason and appear in the exception list, in neither the numerator nor the
denominator, until T16b lands the mandate surface.

### D-039 — Anthropic's content-block shape is the internal message format

Every provider needs translating to or from something. Of the candidates,
Anthropic's content-block shape is the most expressive, so it loses least in
translation: an OpenAI-compatible backend flattens it, a Gemini backend renames
it, and the Anthropic backend passes it through unchanged.

Choosing the least expressive format would have meant discarding structure at
the boundary and reconstructing it, which is where tool-call fidelity gets lost.

### D-040 — Tool results are batched into one message per turn

Splitting the results of several parallel tool calls across separate messages
trains the model to stop making parallel calls. Since a real agent's call
pattern is part of what is being measured, distorting it in the harness would
corrupt the result.

### D-041 — Out-of-scope tools return 404, they are not silently dropped

An agent that reaches for a tool its scope excludes sees the same
`NOT_FOUND_ERROR` a real API would return. Dropping the call instead would make
the tool-scoping ablation measure nothing, because a scoped agent and an
unscoped one that never tried would look identical in the transcript.

What the agent *attempted* is the signal; the refusal is the defense working.

### D-042 — The call budget is enforced mid-batch, not just between turns

A turn emitting five tool calls when one remains in the budget would otherwise
overshoot. The runner stops executing within the batch. Without this the
denial-of-wallet ceiling would be advisory rather than real.

---

## Kavach

### D-043 — Kavach is never given ground truth

A gateway holding the scenario's answer key would score perfectly and prove
nothing. Every rule is one a real merchant could configure without knowing what
the attack is: spend caps, destination provenance, approval thresholds, generic
PII patterns.

The PII detector is deliberately regex over email, phone, card and PAN shapes
rather than the scenario's own `pii_markers`, because a real gateway does not
know which customer it is protecting.

### D-044 — The taint rule is about destinations, not prose

Attackers do not need the agent to quote them; they need it to *act* on them,
and acting means passing an identifier into a money-moving argument. So the
enforced rule is narrow: an identifier that has only ever appeared inside
untrusted text is not a legitimate destination.

This needs no attempt to parse intent out of language, and it produces no false
positive on a legitimate refund, because `create_refund` names a payment rather
than a destination. Trusted provenance wins over untrusted when a value appears
in both -- a value seen in a trusted field is legitimate however else it also
appeared.

### D-045 — Escalation is a deferral, not a denial

Discovered by measurement. With approval counted as a block, benign utility
read 0% and Kavach looked like a gateway that stops all legitimate work.

An approval hand-off is a request for a human, not a refusal. `ToolCall`
records which defense blocked it, and the scorecard reports an escalation rate
separately from attack resistance. The honest statement a merchant needs is
"blocks X% of attacks and needs human review on Y% of legitimate work", and
collapsing the two hides the second number entirely.

### D-046 — The approval threshold sits below the hard spend cap

Also found by a failing test. With the payout cap and the approval threshold
both at Rs 1,00,000, the approval gate could never fire for payouts because
spend always caught it first.

They are different controls: a cap means never, a threshold means ask. A cap at
or below the threshold makes the threshold unreachable.

### D-047 — The units defense needs an observed reference, and says so

Kavach detects a clean 100x gap by comparing a refund against the payment it
settles, using amounts seen in ordinary tool traffic rather than ground truth.

It therefore only fires if the agent looked at the payment first. An agent that
refunds blind gets no protection, which is a genuine limitation and belongs in
the report rather than buried. T33b addresses it by letting the gateway fetch
the reference itself.

### D-048 — Defense order is destinations, spend, units, approval, idempotency, PII

Hard prohibitions first, then anomaly detection, then hand-offs. An amount above
the cap is refused outright, so asking a human about it would be wrong. The
attributed defense is whichever fired first, which is what makes the ablation
table readable.

### D-049 — A transcript must carry everything needed to replay it

Found by the live-versus-replay validation, which is exactly what it was built
to catch. Replay re-dispatched calls the runner had refused as out of the
agent's tool scope, so `fetch_all_payments` errored live but succeeded in
replay, inflating the out-of-scope-read violation class by one episode across
every policy column.

The transcript records `tools` -- the agent's allowed set -- and replay refuses
anything outside it with the same 404 the runner returns. The general rule: if
replay needs to know something to reconstruct a run faithfully, that thing
belongs in the transcript rather than in an object replay happens to have.

After the fix, replay and live agree exactly on attack success across all eight
policy configurations.

### D-050 — Replay is a lower bound on attack success, not an upper bound

D-021 originally had this backwards, which would have discredited every number
built on it.

When a policy blocks the harmful call, the replay records no harm and scores the
attack as failed. A real agent would have seen a refusal it never actually saw,
and might have retried by another route and succeeded. True attack success under
that policy is therefore at least what replay reports.

Replay is optimistic about the defense. `Fidelity.LOWER_BOUND` marks exactly the
episodes where this applies: at least one call blocked, with further calls after
it. An episode where nothing was blocked, or where the block was the final call,
is `EXACT` because there is no counterfactual remainder.

Kavach never blocks reads, only writes, which is what makes the exact case
genuinely exact: with no writes blocked, the agent's information state and the
sandbox are identical to the recording.

---

## Agents and compliance

### D-051 — Prompt hardening is an ablation axis, not a baseline

`hardened()` prepends a preamble telling the agent that tool data is a claim to
evaluate rather than a command to obey, and changes nothing else. Keeping it a
transformation rather than a separately written prompt means the two variants
differ in exactly the preamble, so the ablation measures the preamble rather
than an incidental rewrite.

"Does telling the model to be careful actually work" is the first question
anyone asks about prompt injection and is almost never measured. Now it is a
row.

### D-052 — Agents are written the way a competent engineer would write them

Clear instructions, sensible tool access, nothing about untrusted data. A
harness that only breaks strawmen proves nothing, and one that only tests
pre-hardened agents cannot show what hardening is worth.

The prompts do state that amounts are in paise, for the same reason the tool
descriptions do (D-013): a unit error has to be the agent's fault, not the
harness's.

### D-053 — The sandbox accepts non-compliant mandate debits

The rails reject an unknown or inactive mandate, a non-positive amount, and an
amount above the ceiling authorised at registration, so the sandbox does too.

It accepts a debit with no 24-hour pre-debit notice, a debit after the customer
opted out, and a high-value debit without per-transaction AFA. Those are
merchant obligations under the RBI framework, audited after the fact rather
than blocked in flight, and a non-compliant debit succeeds and looks like
ordinary revenue. Blocking them in the sandbox would have made the whole RBI
category untestable, which is the same trap as D-006.

### D-054 — A compliance breach is critical severity with zero blast radius

No money leaves the merchant when a mandate is debited non-compliantly -- money
comes *in*. The harm is a regulatory penalty and customer detriment, not a
balance change.

Reporting it inside blast radius would corrupt a rupee figure that means "money
the merchant lost". It is counted separately, at critical severity, so it cannot
be waved away as a technicality either.
