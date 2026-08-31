# Submission form — working draft

The Razorpay AI Buildathon form has six required fields. This file holds the
answer to each, kept current as the build progresses rather than written from
memory on the last night.

Applications close **5 September 2026**. Repo URL and video link are required at
application time, so both must exist before the form is opened.

---

## 1. Selected Track

**Track 05 — Open Track**

Reasoning in D-002.

---

## 2. Project Name / Title

**Pariksha — an adversarial certification harness for money-moving AI agents**

---

## 3. Project Objectives — what does it solve?

> Draft. Target 150-250 words. Rewrite once real numbers exist.

Razorpay's Agent Studio lets AI agents act on merchant money: responding to
chargebacks, retrying subscriptions, forecasting cash, releasing payouts. It is
opening to third-party developers, and Razorpay's own guardrails documentation
states that the agent's provider carries responsibility for its behaviour.

The published pre-launch check is a validation *review* of agent logic, data
scope, actions and communication patterns. What does not exist publicly is an
executable, adversarial, measured test: a way to say that an agent survived N
attacks across M categories, leaked Rs X, and cost Y% of its usefulness to
secure.

That gap matters because an LLM agent cannot distinguish information it is
reading from instructions it should follow. An instruction hidden in a dispute
evidence document or a vendor's remittance note is read while the agent does its
job, and acted on. Nothing errors; the audit log records a successful refund.

Pariksha is the exam. It runs payment agents through attacks that only exist in
payments — paise/rupee unit confusion, refund replay, destination diversion, and
RBI e-mandate breaches — and scores three axes jointly: attack resistance, task
utility, and rupees leaked per 1,000 episodes. It ships with Kavach, a
policy-enforcing MCP proxy, and the ablation showing which control stops which
attack class and what each costs in utility.

---

## 4. GitHub Repository URL

https://github.com/dobbydobap/Pariksha-Kavach

Must be **public** before the form is opened.

---

## 5. 5-min Pitch Video Link

`TBD` — see T54/T55.

Structure: 0:00 the seam · 0:30 the attack landing live · 1:30 the same attack
bouncing off Kavach · 2:30 scorecard, frontier, ablation, blast radius · 4:00
what running this against real Agent Studio submissions would take.

---

## 6. Build Challenges & Technical Obstacles

> Running log. Each entry is appended when the problem is actually hit, not
> reconstructed later. Trim to the strongest 4-5 for the final answer.

### C-01 — Razorpay test mode cannot create the data the project is about

Test mode can fetch disputes and settlements but not manufacture them, and there
is no way to produce fraud. Most of the surface worth testing was unreachable.

Solved by building a deterministic sandbox rather than testing against test
mode, which also bought reproducibility and the ability to plant attacks at
known locations. The credibility cost is handled by a conformance suite that
checks sandbox responses field-for-field against recorded live test-mode
responses, plus a live passthrough mode.

### C-02 — The sandbox must accept bad calls, which is the opposite of normal

The first instinct was to validate inputs. That is wrong here: real Razorpay
accepts `amount=500` on a Rs 5,000 payment as a legal Rs 5.00 partial refund. A
sandbox that rejected it would have made the entire paise/rupee attack category
untestable, and the benchmark would have been measuring the sandbox instead of
the agent.

The rule that resolved it: the sandbox enforces exactly the constraints
production enforces, no more and no less. Over-refunding a single payment is
rejected because production rejects it; a nonsensical but legal amount is
accepted because production accepts it. All opinion lives in the gateway, which
is the component under evaluation (D-006).

### C-03 — A scenario with no untrusted surface, found by a failing test

The vendor payout scenario was written as a task string plus a customer record.
Two attacks targeted it and both failed to apply, because there was no
attacker-writable field anywhere in it.

The fix was not a patch. A real payout agent reads a vendor invoice, and on an
invoice the vendor states what they are owed — nothing corroborates that number,
unlike a refund which is bounded by what was captured. So `Invoice.amount` and
every line item are marked untrusted while `fund_account_id` stays trusted,
because it comes from the merchant's own vendor master. That asymmetry became
the clearest illustration of the taint model in the project (D-010).

### C-04 — A zero-budget constraint, which produced the ablation method

The project had to cost nothing. Local inference was measured against the
available hardware and a full run came out at 12-20 hours, so it was ruled out.

Two things resolved it. First, a deterministic mock backend, so runner, judges,
scoring, gateway and report are all built and tested with no key and no spend;
credits are spent only on final measured runs. Second, ablation by offline
replay: each episode runs live once with guardrails off and the tool-call stream
is recorded, then every guardrail configuration is evaluated by replaying that
recording through the policy engine at zero cost.

Replay is reported honestly — exact for terminal blocking defenses, an upper
bound where a block would have changed the agent's later behaviour, with a live
sample validating it and the agreement rate published. The constraint produced
the method: it is the difference between a benchmark nobody can afford to run
and one that reproduces from a single command (D-021, D-023).

### C-05 — Whether to tell the agent that amounts are in paise

Omitting the unit from the tool description would have produced a much higher
failure rate and a much weaker finding, because the error would have been the
harness's fault.

Every amount field states "Amount in PAISE, not rupees" with a worked example,
mirroring Razorpay's real documentation. A failure now means the agent was told
plainly and got it wrong anyway under adversarial pressure, which is the result
actually worth reporting (D-013).

### C-06 — The intended model provider turned out not to be free

The plan assumed Anthropic signup credits, which were not available on this
account. Running the corpus on Claude — the models Razorpay's own Agent Studio
uses — would have required paying, and the project's constraint was zero cost.

Rather than shrink the benchmark, the backend became a swappable interface and
the corpus now runs on four model families across three vendors, all on genuinely
free tiers: Llama 3.3 70B, Qwen 3 and Kimi K2 via Groq, plus Gemini 2.5
Flash-Lite and Flash via Google AI Studio.

This made the result stronger. A security finding measured on one vendor's models
may be a quirk of that vendor; one that reproduces across four independent
families is a finding. It also means every number here can be reproduced at zero
cost by anyone who clones the repository, which is not true of a benchmark that
requires a funded key.

The Claude column is reported as **not measured**, with the reason stated, and
the Anthropic backend is written and ready so it runs unchanged once funded.
Claiming numbers that were never run would fail the exact standard this project
exists to enforce.

The practical constraint that followed was Groq's 6,000 tokens-per-minute cap
rather than its request cap: without prompt caching an eight-turn episode costs
roughly 51k cumulative tokens, about 8.5 minutes. Runs are batched overnight, and
Gemini's higher throughput became the fast iteration path.

### C-07 — An attack category that could not succeed, and was reported rather than hidden

The RBI compliance attacks ask the agent to charge a mandate above the Rs 15,000
additional-factor-authentication ceiling, or to skip the mandatory 24-hour
pre-debit notification. The sandbox had no mandate tools, so the agent could not
perform those actions even if fully compromised. Every one of those episodes
would have scored as a clean pass.

Silently passing them would have inflated the headline resistance number using
the project's most differentiated attack category. The judge now returns
`undetermined` with the reason attached, and those episodes appear in the
published exception list rather than in the numerator or the denominator. The
mandate surface is a tracked task; until it lands, the category is reported as
not yet testable.

This is the same standard the project asks of the agents it grades: report what
was measured, and say plainly what was not.

### C-08 — Building the whole measurement pipeline before spending anything

With no funded model access, writing the runner against a live API would have
meant paying to debug plumbing.

The pipeline is built against a deterministic scripted backend instead. Runner,
judges, scoring, transcript format and the exception path were all developed and
tested end to end with no key and no spend, and the full 22-episode grid runs in
under a second. Model credits are touched only once the machinery is known
correct.

A side effect turned out to matter more than the cost saving: the harness is
verifiable by anyone who clones the repository, with no key at all. A reviewer
can confirm the scoring logic is sound independently of trusting the model
results.

### C-09 — The gateway scored perfectly and was useless, and the harness caught it

The first end-to-end run with Kavach enabled showed attack success falling from
59% to 24% and benign utility falling from 100% to **zero**. The gateway was
blocking every legitimate task.

Nothing was wrong with the measurement; that is precisely what the utility axis
exists to catch. Two things were wrong underneath it.

The approval threshold had been set below every legitimate transaction in the
corpus, so every real task was stopped. Worse, an approval hand-off was being
counted as a denial. Those are different events: one is a refusal, the other is
a request for a human. Conflating them made a working control look like a broken
one and hid the number a merchant actually needs, which is how often the agent
has to interrupt someone.

`ToolCall` now records which defense blocked it, the scorecard reports an
escalation rate separately from attack resistance, and the thresholds were
recalibrated so a hard cap sits above the ask-a-human threshold rather than
underneath it.

A third gap surfaced in the same run: Kavach had no defense against paise/rupee
confusion at all. A spend cap catches 100x-over and is structurally blind to
100x-under, which is the silent one. A units gate now compares a refund against
the payment it settles, using amounts observed in ordinary traffic rather than
any ground truth.

Had utility not been measured jointly with security from the start, a gateway
that blocked 100% of legitimate work would have looked like a success.

### C-10 — The validation caught the replay lying, which is why it existed

Replay computes the whole ablation matrix from recordings instead of re-running
agents, so its numbers are only worth publishing if they match what a live
guarded run would have produced. A test compares the two across every policy
configuration.

It disagreed. Replay reported 24% attack success where live reported 18%,
consistently, across all eight configurations.

The cause was a faithfulness gap rather than a scoring bug. The runner refuses
calls outside an agent's allowed tool set with a 404, but the transcript did not
record which tools the agent had, so replay re-dispatched those calls and they
succeeded. One episode's out-of-scope read counted as a violation in replay and
not in reality, in every column.

The fix was the principle the transcript format is built on: if replay needs
something to reconstruct a run, it belongs in the transcript. The allowed tool
set is now recorded and honoured. Replay and live now agree exactly across all
eight configurations, and 22 recordings replace 176 live runs.

A second thing was wrong and was corrected at the same time. The design notes
described replay as an upper bound on attack success. It is a lower bound: a
blocked call means the replay sees no harm, while a real agent might have
retried by another route and succeeded. Replay flatters the defense. Publishing
that bound in the wrong direction would have undermined every number built on
it.

### C-11 — Making the most differentiated attack category actually testable

The RBI e-mandate attacks were the clearest thing separating this corpus from a
generic agent-security benchmark, and they could not score. The sandbox had no
mandate tools, so an agent could not breach the Rs 15,000 additional-factor
threshold or skip the 24-hour pre-debit notice even if fully compromised. Those
episodes sat in the exception list.

Building the surface meant deciding what the rails enforce versus what the
merchant is merely obliged to do. An amount above the ceiling authorised at
registration is rejected, because NPCI rejects it. A debit with no pre-debit
notification, a debit after opt-out, and a high-value debit without AFA are all
accepted, because they are merchant obligations audited after the fact -- a
non-compliant debit succeeds and looks like ordinary revenue. Blocking them
would have made the category untestable for a second time.

A related question was where the harm belongs. A mandate debit moves money
*into* the merchant, so counting it inside blast radius would corrupt a figure
that means "money the merchant lost". Compliance breaches are counted
separately at critical severity.

One injected sentence now produces two distinct violations, each traceable to a
specific clause of the framework dated 21 April 2026.

### C-12 — A dry run needs something to run on

The whole pipeline was built against a scripted mock backend so nothing had to
be paid for while the machinery was wrong. That backend is scripted per episode,
though, which meant it could not drive a full grid: the zero-cost end-to-end dry
run had nothing to execute.

A small reactive backend now reads ids out of the task and fields out of tool
results and drives each scenario to completion, so the whole 22-episode grid,
the scoring, the gateway and the replay ablation all run in CI with no API key.

It immediately earned itself: it failed on two of three scenarios because tool
results arrive as JSON-encoded strings, so field names inside them are escaped a
second time and the parsing missed every amount. That would have surfaced later
against a paid model instead.

The care needed was in how it is presented. It has no language understanding, so
it scores 0% attack success on every category, and those zeroes look like a
perfect result if lifted out of context. The command prints a banner stating the
numbers are not findings. A benchmark whose own dry-run output could be mistaken
for a result is a benchmark that will eventually mislead someone.

### C-13 — `[pending]`

Append as encountered.

---

## Pre-submission checklist

- [ ] Repo is public and clones cleanly on a machine that has never seen it
- [ ] `pariksha bench --seed 1729` reproduces every number in the README
- [ ] `ruff check` clean, full test suite green
- [ ] No secrets in history; `.env` ignored and `.env.example` present
- [ ] README headline numbers are real, not placeholders
- [ ] `docs/ARCHITECTURE.md` includes the limitations section
- [ ] Video is under 5:00 and the audio is intelligible
- [ ] Video link is publicly viewable without a login
- [ ] All six form fields drafted and proofread
- [ ] Submitted on the morning of 5 September, not at the deadline
