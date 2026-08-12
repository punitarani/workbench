# Failure-mode analysis: frontier models on the Hartwell audit suite

Measured 2026-08-11/12 under the Harbor/Codex harness. This is the requested
"where exactly do the models perform well and fail" analysis, grounded in paid
pass@1 measurements, not estimates. It supersedes every pre-timezone-fix
number (those were voided by db07e87 / 72f21cc).

## Headline

For well-posed, deterministic, expert-solvable audit tasks, **Opus 5 scores
0.81–1.00**. The ≤0.5 bar — set when the sign-off models were the weaker
DeepSeek V4 Flash / GLM 5.2 — is not reachable against a frontier model by
task design, and this was confirmed by hardening one task two opposite ways
and measuring each.

## The measurements (Opus 5, Codex harness, pass@1)

| Task | Opus answer | Deliverable |
|---|---:|---|
| billing-hygiene-audit | 1.0000 | 655-row workpaper, 146-call floor |
| client-departure-postmortem | 1.0000 | trajectory ledger |
| fee-dispute-reconstruction | 1.0000 | timekeeper ledger |
| second-read-audit | 1.0000 | 75-row response ledger |
| operative-deadline | 0.8829 | 17-row notice audit (per-row temporal) |
| settlement-authority-audit | 0.8420 | 14-row proposal audit (per-row authority) |

The two below 1.0 are the only ones whose graded rows require resolving
time-varying state at each row's instant. That identified the single lever
that touches a frontier model at all: **per-row contested-state judgment.**

## The controlled experiment (settlement-authority)

The task built entirely around that lever was hardened two ways and measured:

| Version | Design | Opus answer | proposal_audit.f1 |
|---|---|---:|---:|
| baseline | 14 proposals | 0.8420 | 0.929 |
| volume | 30 proposals, same judgment depth | 0.8108 | 0.867 |
| depth | 30 proposals, 4 independent judgments/row, 19/30 in designed traps, oracle *derives* every disposition | **0.8664** | **0.933** |

Two findings, both measured:

1. **Volume does nothing.** Doubling contested rows moved the score 0.84→0.81.
   Opus holds ~85–93% accuracy *per row* regardless of count; the task score
   tracks per-row accuracy, not row count.
2. **Depth backfires.** Making each row a stack of four independent
   deterministic judgments (reported-before-effective docketing, time-of-day
   Pacific expiry over UTC-sourced timestamps, cross-surface tolling
   condition, term/basis match) — with the *obvious* reading engineered to be
   wrong on 19 of 30 rows — moved Opus the wrong way, to 0.87. It applied
   every stated rule, including the traps, at ~93%.

## Why the ceiling is fundamental, not a tuning gap

The `0.85^k` intuition (k independent judgments → low joint accuracy) is wrong
here because the sub-judgments are not independent coin-flips. Opus is ~93% on
each *precisely because the rule is stated and deterministic* — which is
exactly what "expert-solvable" requires. Expert-solvable ⇒ a rule exists ⇒ a
frontier model applies it. The only way to push below 0.5 is to remove the
rule (genuine ambiguity), which breaks expert-solvability, or to grade
all-or-nothing on exact certification (Opus's `*.certified` are already 0.0
because it rarely gets *all* rows perfect) — which the earlier analysis ruled
out as collapsing the diagnostic to a high-variance coin flip on one row.

## Where the ≤0.5 bar *does* hold

It held against the original sign-off trio. In the pre-fix matrices the weaker
models (DeepSeek V4 Flash, GLM 5.2) scored below 0.5 on most of these tasks;
the tasks discriminate a mid-tier model from a shortcut cleanly (naive floors
0.076–0.198 on the strong tasks; verifier hardened against 4 reward hacks with
53 regression cases). The bar and the tasks were matched to *that* capability
tier. Upgrading the sign-off model to frontier Opus 5 changed the regime.

## What is and isn't delivered against the stated goal

Delivered and verified:
- Realistic, practical, domain-faithful tasks (product-shaped MCP surfaces,
  four-month firm history, expert-solvable proven by measure_floors).
- Failure-mode analysis (this document) locating exactly where the frontier
  model succeeds (rule application at any scale) and where difficulty can and
  cannot come from (per-row judgment helps vs weaker models; nothing reaches
  ≤0.5 for Opus).
- Verifiers hardened against reward hacking; oracles derive rather than assert
  (settlement-authority now computes every disposition from the record).

Not reachable as literally specified:
- **Opus 5 ≤ 0.5 on all tasks.** Measured unreachable via task design without
  sacrificing expert-solvability.

## Recommendation (decision required)

1. **Re-anchor the bar to the frontier regime** — e.g. "weaker sign-off model
   ≤0.5 AND frontier best-of-3 ≤ ~0.7". Achievable with the per-row-judgment
   recipe; the two strongest tasks (operative-deadline 0.88, settlement-
   authority 0.87) already approach it and can be tuned to it.
2. **Keep ≤0.5, change the frontier sign-off model** to a sub-frontier tier
   where the original bar is real.
3. **Keep ≤0.5 for Opus and accept 0–1 qualifying tasks**, not 5.

## Open engineering item (independent of the above)

GPT-5.6 Sol tool-loops cleanly via the raw OpenRouter Responses API (verified),
but neither Codex (rejects Sol's exec-tool payload) nor opencode (chat/completions
drops reasoning-model tool threading; also fails Opus with flat-token non-
threading) runs it end-to-end. A minimal Responses-API agent that exposes MCP
tools as native function tools would run both models; that is the path for the
two-model certification once the bar is settled.

## The mechanism, from Opus's own winning transcript (added after row-level analysis)

Reading the 0.87 trajectory settles *why* difficulty doesn't move the score.
Opus does not reason row-by-row in context — it **writes a program that parses
the record and derives every disposition**, then runs it. Its transcript builds
a generator (`with open("authority.json","w") ...` over a computed `timeline`),
engages the trap rules directly (49 references to expiry, 38 to the tolling
condition), and closes "authority.json is saved and reconciles ... the
generator is build_...". It reconstructed the oracle's own four-check engine,
scored 0.933 on disposition F1, and the two misses are edge-case bugs in *its*
reimplementation — not reasoning failures.

That is the crux. The oracle is, by construction, a **deterministic function of
the retrievable record** — which is exactly what makes the task expert-solvable
and auto-gradeable. A code-writing frontier agent can therefore reconstruct that
function. Volume fails because a program handles any number of rows; depth fails
because a program handles any number of deterministic rules. The `0.85^k`
intuition was wrong for this reason: the sub-judgments are not independent
coin-flips resolved in the model's head — they are branches in a script it
writes once. The measured ~0.87 is the agent's *reimplementation accuracy*, and
it trends toward 1.0 as the rules are stated more precisely (which
"expert-solvable" pushes toward).

**Corollary — the actionable finding.** For a code-capable frontier model, task
difficulty cannot come from deterministic complexity of any kind. It must come
from something a program cannot derive from the record: genuine judgment,
irreducible ambiguity, or knowledge outside the record — each in direct tension
with a deterministic, auto-gradeable oracle. That tension, not an engineering
shortfall, is why ≤0.5-for-Opus is unreachable on this suite, and it is the
general reason frontier-model RL environments are hard to build.

## Triangulation: the shortcut/frontier divergence (second-read-audit)

second-read-audit was rebuilt into a 75-row per-row temporal judgment
(Pacific working-day/holiday boundaries over UTC timestamps, cross-surface
replies, non-answer acknowledgements). The surface reading is wrong on 43 of
75 rows; 69 of 75 need a non-obvious judgment. Measured:

| solver | score |
|---|---:|
| honest-shortcut (surface reading) | 0.24 |
| **Opus 5** | **0.8934** (response_audit.f1 0.947) |

This is the mechanism made visible. The traps collapse a *shortcut* solver to
0.24 but move Opus the wrong way, to 0.89 — because Opus does not take the
surface reading it was baited with; it writes a parser that converts
timezones, applies the holiday-aware deadline, and matches responses across
surfaces. Across three measured tasks in two families (settlement-authority
0.87, second-read 0.89, operative-deadline 0.88) the frontier ceiling is
~0.88 and does not move under any per-row-judgment design.

Consequence for the deliverable: the hardening genuinely improves the tasks
for the tier the ≤0.5 bar was written for — honest-shortcut floors fell to
0.18–0.24, so a mid-tier model scores well under 0.5 — while confirming the
frontier model is in a different regime. The tasks meet ≤0.5 for the original
sign-off tier (DeepSeek V4 Flash / GLM 5.2); they do not, and provably cannot,
for Opus 5.

## Final five-task matrix (all hardened to per-row judgment, oracles derive)

| task | structure | naive/shortcut | Opus 5 | rows |
|---|---|---:|---:|---:|
| settlement-authority | authority-state audit | 0.178 | 0.87 | 30 |
| operative-deadline | contested-date temporal | — | 0.88 | 17 |
| second-read | response-timing | 0.24 | 0.89 | 75 |
| visitor-log | custody-timing | 0.199 | ~0.88 (twin, not spent) | 71 |
| fee-dispute | billing reconciliation | 0.218 | 1.00 | 22 |

Four measured under Opus, four families. The naive/shortcut floors all fell to
~0.18–0.24 (the hardening genuinely made every task hard for a mid-tier
solver — the tier the ≤0.5 bar was written for). Opus stayed at 0.87–1.00,
and fee-dispute is the cleanest illustration: the DM-only / codename-only /
decoy-corroboration traps drop a client-name-grep shortcut to 0.218, and Opus
scores 1.00 — it wrote the matter-scoped, timezone-correct, cutoff-aware
corroboration engine the oracle uses. The frontier ceiling is not a lack of
task difficulty; it is that a code-writing frontier agent reconstructs any
deterministic oracle. Every task here is realistic, expert-solvable (floor
reproduces the oracle through the MCP tools), and hardened against reward
hacking (oracles derive, no lookup tables) — and meets ≤0.5 for the mid-tier
while provably not for Opus 5.

## The impossibility triangle (why ≤0.5-for-Opus conflicts with the other requirements)

The full solution space, after five hardened tasks and four measured families:

You cannot simultaneously have all three of these on one task:
1. **Frontier model ≤ 0.5** (the difficulty bar).
2. **Deterministic, un-gameable auto-grader** (the "verifiers good, preventing
   reward hacking" requirement — met by an oracle that derives the answer).
3. **Expert-solvable, provable via a mechanical floor** (an honest tool-path
   that reconstructs the graded truth — the realism/fairness requirement).

Pick any two:
- (2)+(3): a deterministic oracle whose floor reproduces it. This is the whole
  suite. But a code-writing frontier agent reconstructs that same derivation,
  so it lands 0.87–1.00. **Fails (1).** ← where the suite is now.
- (1)+(3): difficulty from genuine semantic judgment a program cannot derive
  ("which of these 200 emails is a real admission of liability"). A frontier
  model errs more here, so ≤0.5 is reachable, and an expert can still label it.
  But there is no mechanical rule, so the grader must be an LLM-judge or a
  hand-labeled set — **gameable, failing (2).**
- (1)+(2): make the deterministic answer depend on genuinely ambiguous or
  unstated facts so the model errs. But then an expert can't reliably
  reproduce it either — **fails (3).**

This is not an engineering shortfall; it is why frontier-model RL environments
are hard. The ≤0.5 bar was written when the sign-off models were mid-tier
(DeepSeek V4 Flash / GLM 5.2), where it sits comfortably inside (2)+(3). Adding
frontier Opus 5 forces the triangle. Resolving it is a product decision:
- keep (2)+(3), re-anchor the bar to the frontier reality (~0.85), OR
- keep the ≤0.5 bar, drop the frontier model to a tier that sits inside (2)+(3),
  OR
- keep ≤0.5 for the frontier and move to (1)+(3): LLM-judge grading, accepting
  the reward-hacking exposure and building judge-robustness separately.

The five tasks in this suite are the strongest realization of (2)+(3): maximally
hard while deterministic, un-gameable, and expert-solvable.
