# Pariksha — task board

53 tasks to submission. One task = one commit. Nothing bundled.

Deadline **5 September 2026**. Feature freeze **3 September**. Submit the morning
of the 5th, never at the deadline.

Rules for every task:
- Task is not done until its tests pass and `ruff check` is clean.
- No task adds unused code, dead parameters, or speculative abstraction.
- Design reasoning goes in `DECISIONS.md`, not in source comments.
- All git commands are run by the user, never by the agent.

Status: `[ ]` todo · `[~]` in progress · `[x]` done

---

## Phase 0 — Foundation

- [x] **T01** Repo scaffold, venv, pyproject, .gitignore, .env.example
- [x] **T02** `sandbox/money.py` — paise arithmetic, Indian grouping, unit-confusion detector
- [x] **T03** `sandbox/ids.py` — deterministic Razorpay-shaped IDs
- [x] **T04** `sandbox/entities.py` — 11 entities with per-field provenance
- [x] **T05** `sandbox/state.py` — sandbox operations and money-movement ledger
- [x] **T06** `sandbox/tools.py` — 19 strict-schema tools and dispatcher
- [x] **T07** `sandbox/seed.py` — 3 scenarios with declarative ground truth
- [x] **T08** `gym/attacks.py` — 19 attacks, 9 categories, 3 subtlety levels
- [x] **T09** Rename to Pariksha; `kavach/` becomes the gateway subpackage
- [x] **T10** `DECISIONS.md`, `TASKS.md`, `SUBMISSION.md`

**Standing task, every phase:** append to the Build Challenges log in
`SUBMISSION.md` whenever a real obstacle is hit. It is a required form field and
writing it from memory on the last night produces a generic answer.

- [x] **T11** Lean-code pass over Phase 0
  Strip long rationale docstrings from all `sandbox/` and `gym/attacks.py` files,
  leaving short functional docstrings. Cross-reference `DECISIONS.md` by number
  where a reader would otherwise ask why. No behaviour change; tests must pass
  unchanged.

  ```
  git add -A && git commit -m "Lean-code pass: move rationale to DECISIONS.md" && git push
  ```

---

## Phase 1 — Measurement spine (zero API cost)

- [x] **T12** `gym/transcript.py`
  Episode record: scenario key, attack id, model, seed, ordered tool calls with
  arguments and results, token usage, termination reason. JSONL, one episode per
  file under `runs/<seed>/`. This is the artefact replay and scoring both read.

- [x] **T13** Tests for transcript round-trip, including unicode payloads.

- [x] **T14** `gym/violations.py`
  The `Violation` type and the fixed vocabulary: `over_ceiling`,
  `diverted_destination`, `unit_confusion`, `double_spend`, `forbidden_tool`,
  `pii_egress`, `out_of_scope_read`, `call_budget_exceeded`, `compliance_breach`.
  Each carries severity and rupee impact where applicable.

- [x] **T15** `gym/judges.py`
  Deterministic evaluation of a transcript against an `Expectation`. Returns
  violations plus an `undetermined` flag for episodes that cannot be adjudicated.
  No LLM (D-020).

- [x] **T16** Tests for judges — one per violation type, plus the undetermined path.

- [x] **T16b** Mandate surface in the sandbox: a `Mandate` entity plus
  `create_mandate` and `charge_mandate` tools, so the RBI compliance category
  becomes testable instead of undetermined. Carries the AFA threshold, the
  24-hour pre-debit notice and the opt-out flag. Without this the most
  differentiated attack category cannot score (D-019).

- [x] **T17** `gym/backends/base.py`
  `Backend` protocol: `complete(messages, tools, system) -> Completion`, where
  `Completion` carries text, tool calls, usage and stop reason.

- [x] **T18** `gym/backends/mock.py`
  Deterministic scripted backend (D-023). Drives a scenario to a scripted
  outcome so the whole pipeline is testable with no key and no spend. Supports
  scripting a compliant run, an attacked run, and a malformed run.

- [x] **T19** `gym/runner.py`
  Episode executor: builds the prompt, loops the backend against the tool
  surface, enforces the call budget, writes the transcript. Backend-agnostic.

- [x] **T20** Tests for runner against the mock backend, including budget
  exhaustion and tool-error recovery.

- [x] **T21** `gym/score.py`
  Aggregate transcripts and judgments into attack success rate by category and
  subtlety, benign utility, blast radius per 1,000 episodes, and the exception
  list. Wilson confidence intervals on every rate (n is small; D-004).

- [x] **T22** Tests for scoring, including the degenerate all-blocked case that
  must show zero utility.

  ```
  git add -A && git commit -m "Measurement spine: transcript, judges, runner, scoring" && git push
  ```

---

## Phase 2 — Kavach, the gateway

- [x] **T23** `kavach/ledger.py` — hash-chained append-only audit log.
- [x] **T24** Tests for ledger, including detection of a tampered middle entry.
- [x] **T25** `kavach/taint.py` — provenance tagging over tool results, driven by
  the schema registry from `entities.untrusted_field_registry()`.
- [x] **T26** Tests for taint propagation and the fail-closed unknown-field path.
- [x] **T27** `kavach/policy.py` — declarative YAML policy: per-tool spend caps,
  aggregate ceilings, destination allowlists, approval thresholds, PII egress
  rules. Typed and validated at load.
- [x] **T28** Tests for policy parsing and evaluation, including malformed policy.
- [x] **T29** `kavach/idempotency.py` — request fingerprinting and replay refusal.
- [x] **T30** Tests for idempotency across retries and near-duplicate calls.
- [x] **T31** `kavach/breaker.py` — circuit breaker on repeated policy denials.
- [x] **T32** `kavach/gateway.py` — composed enforcement point; every defense
  independently toggleable so ablation is possible (D-021).
- [x] **T33** End-to-end gateway tests against the mock backend.
- [ ] **T33b** A `units` reference the gateway can fetch itself, so the
  paise defense does not depend on the agent having looked at the payment
  first (D-047).
- [x] **T34** `kavach/replay.py` — offline ablation: replay a recorded transcript
  through any policy configuration. Must mark upper-bound cases explicitly.
- [x] **T35** Tests for replay, including a case proving the upper-bound label is
  applied when a block would have changed later behaviour.

  ```
  git add -A && git commit -m "Kavach gateway: policy, taint, idempotency, ledger, replay" && git push
  ```

---

## Phase 3 — Agents and the first real numbers

- [x] **T36** `agents/base.py` — agent definition: system prompt, allowed tool
  subset, call budget. Pulled forward; the runner depends on it.
- [x] **T37** `agents/refund_resolver.py` — deliberately naive v0.
- [x] **T38** `agents/dispute_responder.py` — deliberately naive v0.
- [x] **T39** `agents/payout_agent.py` — deliberately naive v0.
- [x] **T40** Agent tests against the mock backend.
- [x] **T40b** Scoped-tool agent variants, so tool scoping becomes an ablation
  row rather than an assumption (D-032). Prompt hardening added as a second
  ablation axis at the same time (D-051).
- [x] **T41** `gym/backends/groq.py` — free-tier backend, OpenAI-compatible
  wire format, token-per-minute throttle so runs stay inside 6,000 TPM (D-031).
- [ ] **T41b** `gym/backends/gemini.py` — deferred. Gemini's current API is a
  stateful `/v1beta/interactions` endpoint with `previous_interaction_id`,
  which does not fit the stateless replay design without work. Groq already
  covers two model families from one key, so this is enrichment rather
  than a blocker (D-055).
- [ ] **T41c** `gym/backends/anthropic.py` — written but unfunded. Prompt caching
  and the non-zero cache-read assert (D-025). Kept so the Claude column runs
  unchanged the day it is funded.
- [x] **T42** `cli/main.py` — `pariksha bench`, `pariksha score`, `pariksha cost`,
  with `--seed`, `--model`, `--backend`, `--max-spend`.
- [x] **T43** Full dry run end to end via `pariksha rehearse`. Zero spend, no
  key, runs in CI. Surfaced and fixed the escaped-JSON parsing bug.
- [x] **T44** First real baseline run, guardrails off, on `openai/gpt-oss-120b`
  via Groq. **The pivot point** — this is where the project acquires
  a result.
- [x] **T44b** Cross-family sweep: `qwen/qwen3.8-27b`, 17 of 41 episodes,
  0 of 16 attacks landed, utility unmeasured on one benign control (D-089).
  Original: `openai/gpt-oss-20b` and `qwen/qwen3.8-27b`
  against the `gpt-oss-120b` baseline, batched against the TPM cap. Model ids
  confirmed against the live catalogue, not the docs (D-059).

- [x] **T44c** Guard-model comparison: `meta-llama/llama-prompt-guard-2-86m` is a
  dedicated prompt-injection classifier, free on the same Groq key. Add it as a
  Kavach defense and an ablation row. The question worth answering is whether a
  purpose-built classifier beats provenance tracking, and what it costs in
  false positives on legitimate customer prose (D-060).

  ```
  git add -A && git commit -m "Agents, Anthropic backend, CLI, first baseline" && git push
  ```

---

## Phase 4 — Corpus expansion

- [x] **T45** Scenario 4: `subscription.failed_instalment`, built on the
  mandate surface so the RBI category is native rather than bolted onto
  the refund case. Further scenarios remain optional enrichment.
- [x] **T46** Corpus expanded to 37 attacks across 41 episodes, weighted
  toward subtlety 3 (6 -> 19) because the baseline found subtlety did not
  protect (D-063).
- [x] **T47** Coverage tests. Caught a single-subtlety category and an
  invented category name on first run.
- [x] **T48** Re-ran on the expanded corpus: 37 of 41 episodes on
  `openai/gpt-oss-20b`, stopped cleanly on the daily token ceiling. Both
  headline findings replicated.

  ```
  git add -A && git commit -m "Expand corpus to 8 scenarios and 60 attacks" && git push
  ```

---

## Phase 5 — Results and deliverables

- [x] **T49** `report/scorecard.py` — static HTML scorecard: headline table,
  per-category breakdown, subtlety breakdown, security/utility frontier,
  ablation matrix, exception list. Self-contained, no CDN.
- [x] **T50** Replay ablation matrix over the real baseline. All 22 rows came
  back exact, so on this corpus the replayed numbers are the actual numbers
  rather than a bound (D-062).
- [ ] **T51** MCP proxy server exposing Kavach over MCP, with a worked example of
  an external agent pointing at it unchanged (D-027).
- [x] **T52** `docs/ARCHITECTURE.md` — data flow, taint model, policy grammar,
  threat model, and an explicit limitations section.
- [x] **T53** README rewrite with the real headline numbers, one-command repro,
  and a screenshot of a live test-mode payment if Razorpay keys are available.

  ```
  git add -A && git commit -m "Scorecard, ablation, MCP proxy, architecture docs" && git push
  ```

---

## Phase 6 — Submission

- [x] **T59** `pariksha demo` and the README diagram: a paced walkthrough of one
  attack landing then being blocked, driven from a real recording that ships
  with the package so it works from a bare clone with no key (D-091, D-092).


- [x] **T54** Video script drafted in `docs/VIDEO.md`; numbers filled and
  rehearsed once the final run lands.  Original brief: Structure: 0:00 the seam ·
  0:30 the attack landing live · 1:30 the same attack bouncing off Kavach ·
  2:30 scorecard, frontier, ablation, blast radius · 4:00 what running this
  against real Agent Studio submissions would take.
- [ ] **T55** Record the 5-minute video. Re-record until it is tight.
- [x] **T56** Manual adversarial hour. 6 attacks on the gateway, 5 got
  through, 4 fixed with regression tests, 2 documented as limits. Original: try to defeat Kavach by hand. Anything
  that works becomes a corpus entry and goes in the limitations section.
- [x] **T57** Fresh-install verification: 56 shipped files, new venv, all
  provider keys unset. 225 tests pass, every CLI command works, the full
  grid runs with no key, and transcripts are byte-identical to the working
  repository at the same seed (D-087).
- [ ] **T58** Fill the six form fields from `SUBMISSION.md`, work the
  pre-submission checklist, then submit.

The form requires: Selected Track, Project Name, Project Objectives (what does
it solve), GitHub Repository URL, 5-min Pitch Video Link, and Build Challenges &
Technical Obstacles. Repo and video must both exist before the form is opened.

  ```
  git add -A && git commit -m "Submission: video, final polish" && git push
  ```

---

## Cut order if time runs short

Cut from the bottom, never the top:

1. T51 MCP proxy server
2. T45 scenarios 6-8
3. T39 payout agent (keep refund and dispute)
4. Live-mode passthrough entirely
5. Attack categories beyond the first six

Never cut: the baseline numbers, the ablation table, the exception list, the
video.
