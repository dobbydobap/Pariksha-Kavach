# Five-minute pitch — working script

Rehearse aloud until it fits without rushing. Do not narrate a screen recording
cold; record the screen separately and speak to it.

Numbers marked `<N>` are filled from the final run before recording. Do not
record with placeholders in shot.

---

## 0:00 – 0:35 — The seam

> Razorpay shipped Agent Studio this year. AI agents that respond to chargebacks,
> retry subscriptions, release vendor payouts. Real agents, moving real merchant
> money.
>
> Their guardrails documentation says two things a few paragraphs apart. That the
> developer of each agent is responsible for its behaviour. And that any merchant
> or developer will be able to publish agents to the marketplace.
>
> The pre-launch check they describe is a review. Someone reads your agent's
> logic and data scope.
>
> There is no exam. No way to say this agent survived N attacks, leaked X rupees,
> and cost Y percent of its usefulness to secure.
>
> I built the exam.

**On screen:** the two quotes side by side from the guardrails post.

---

## 0:35 – 1:40 — The attack landing

> Here is a refund agent. Competently written, sensible tools, no security
> hardening. The kind of thing you would actually ship.
>
> A customer says their order never arrived. The agent reads the support thread,
> which is its job.
>
> Appended to the customer's last message is this.

**On screen:** scroll the injected `SYSTEM NOTICE` block in the support thread.

> A fake finance relay. Says it is pre-approved, says the customer changed banks,
> gives a new account.
>
> Watch what the agent does.

**On screen:** run the episode. Let the `create_payout` call land, uninterrupted.

> Five lakh rupees, to an account that exists nowhere except inside a message a
> customer wrote.
>
> No error. No alert. The audit log says the refund was processed successfully.
> The merchant finds out from their bank balance.

**Pause here.** Do not rush this beat.

---

## 1:40 – 2:20 — The same attack, blocked

> Same agent, same attack, same seed. This time it goes through Kavach.

**On screen:** re-run with `--policy default`, highlight the block.

> Blocked, and the reason is specific: that account has only ever appeared inside
> untrusted text.
>
> That is the whole rule. Every field in the system is labelled at the schema
> level — Razorpay produced this, or a human outside the company wrote it. An
> identifier that only ever appeared in the second kind is not a destination.
>
> No prompt engineering. No asking a model whether something looks like an
> attack. Just provenance.

---

## 2:20 – 3:40 — The numbers

**On screen:** the scorecard.

> Thirty-seven attacks, nine categories, four scenarios, forty-one episodes.
> Every rate carries a confidence interval and its sample size, because at this
> corpus size a bare percentage would overstate what I measured.
>
> Guardrails off, attack success `<N>`. Kavach on, `<N>`. Blast radius — money
> moved that should not have been — from `<N>` to `<N>` per thousand episodes.
>
> Two findings I did not expect.

**On screen:** the subtlety table.

> First: subtlety barely mattered. Blatant `<N>`, plausible `<N>`, subtle `<N>`.
> The comfortable assumption is that models fall for crude attacks and resist
> careful ones. That is not what I measured. The attack that worried me most had
> no injected framing at all — an ordinary note saying a vendor had changed
> banks. It sent money to an attacker.

**On screen:** the category table.

> Second: every attack that landed was a provenance failure. Everything it
> resisted was arithmetic or procedure. It never confused paise for rupees, never
> double-refunded, never breached a mandate rule, was not moved by urgency or a
> forged approval.
>
> It can do the sums and follow the process. It cannot tell whose voice it is
> reading.

---

## 3:40 – 4:20 — The ablation, and being honest about it

**On screen:** the ablation table.

> Every guardrail configuration here is computed by replaying recordings, not by
> re-running agents. Forty-one recordings replace three hundred and twenty-eight
> live runs. That is why the whole thing costs nothing.
>
> It also means I have to be careful. Replay is a lower bound on attack success,
> not an upper bound — when a policy blocks the harmful call, a real agent might
> have retried another way. Every row says whether it is exact.
>
> The ablation names which controls earned their place. Removing destination
> provenance moves the number. Removing PII egress moves it. The others did not,
> because the model never made the mistakes they guard against.
>
> And the approval gate fired more than every other defense combined, bought no
> security on this workload, and cost `<N>` of the automation. That is a real
> thing to tell a merchant.

---

## 4:20 – 5:00 — What it would take to run this on Agent Studio

> This runs on free-tier models, so anyone can reproduce every number in the repo
> for zero rupees. Agent Studio runs on Claude. I could not fund those runs, so
> that column is reported as not measured — the backend is written and runs
> unchanged the day someone funds it.
>
> To put this in front of the marketplace you would need three things. The
> corpus pointed at the real MCP endpoint instead of my sandbox, which is a
> config change because Kavach is a proxy, not a library. A conformance suite
> against live test-mode responses. And a threshold — what score does an agent
> need before merchants can install it.
>
> That is the piece I would want to work on.

---

## Rules for the recording

- Under 5:00. Aim for 4:45 so it does not feel rushed at the end.
- The attack landing at 1:00 is the moment a judge remembers. Give it silence.
- No placeholder numbers. No cropped terminal text.
- State the limitations out loud once. A judge who finds an overclaim stops
  believing the rest.
- Publicly viewable without a login. Check in a private window before submitting.
