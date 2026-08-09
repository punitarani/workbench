# Spend ledger — four-month history run

Hard cap: $25.00. All LM spend through OpenRouter on the project key.
Prices are OpenRouter list at time of use; DeepSeek V4 Flash 0731 taken at
$0.07/M input, $0.28/M output (flash-class list). Entries are estimates
from measured token usage, rounded up.

| # | When (PT) | What | Tokens (p/c) | Est. cost | Running total |
|---|---|---|---|---|---|
| 1 | 08-08 23:4x | GEPA run 1 (14 rollouts + smokes) | ~208K/28K | $0.03 | $0.03 |
| 2 | 08-09 00:0x | fixcheck + run 2 + holdout (16 rollouts) | ~165K/21K | $0.02 | $0.05 |
| 3 | 08-09 00:1x | demo day re-record #1 (over-corrected) | ~350K/est | $0.05 | $0.10 |
| 4 | 08-09 00:2x | hybrid evals + re-record #2 + run 3 | ~500K/est | $0.08 | $0.18 |
| 5 | 08-09 00:4x | de-overfit eval + holdout3 + run 4 | ~350K/est | $0.05 | $0.23 |
| 6 | 08-09 00:5x | acceptance re-record (original text + rendering fix) | ~350K/est | $0.05 | $0.28 |

| 7 | 08-09 01:1x | Phase 1 tool rebuild (no OpenRouter spend) | 0 | $0.00 | $0.28 |
| 8 | 08-09 | Phase 2 storyline content, 47 pieces (deepseek-v4-flash-0731) | ~6.6K/9.3K | $0.003 | $0.283 |
| 9 | 08-09 | token remeasure pass, 47 calls into a scratch cache (credits delta $0.002445) | 6,635/9,286 | $0.003 | $0.286 |

Phase 2 generation totals: 94 LM calls against the 2,500-call cap; the
87-workday build itself (tiers A and B) spent zero LM calls — all spend is
tier C content authoring. Entry 8's exact usage line was lost to a
truncated pipe; entry 9 re-authored the identical workload (same prompts,
model, seeds, params) to measure it, and its measured tokens stand in for
both rows. Remaining: ~$24.71.

Eval pricing confirmed (OpenRouter, USD/Mtok prompt/completion):
deepseek/deepseek-v4-flash-0731 $0.09/$0.18; z-ai/glm-5.2 $0.07/$0.22;
openai/gpt-5.6-luna $0.10/$0.60. Phase 3 matrix (3 models x 3 attempts
x 5 tasks ~ 45 episodes) projected $2-5 against $24.71 remaining.

| 10 | 08-09 02:4x-03:3x | Eval matrix round 1: 5 tasks x 3 models x 3 attempts + smoke | 11.8M/0.4M | $1.13 | $1.42 |

Round-1 matrix (best-of-3): standard-drift .60/.60/.525, fee-dispute
.30/.30/.85, vanished-clause .75/.75/.75, client-departure .45/.45/.45,
operative-deadline 1.0/1.0/1.0 (DeepSeek/GLM/Luna). One task holds;
four in hardening. Remaining: ~$23.58.
