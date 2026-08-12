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
