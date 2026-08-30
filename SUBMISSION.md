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

https://github.com/dobbydobap/Pariksha

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

### C-06 — `[pending]`

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
