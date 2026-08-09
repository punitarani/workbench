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

| 11 | 08-09 04:0x-04:2x | Eval matrix round 2 (4 tasks x 3 models x 3; logs partially truncated — measured: Luna complete 2.19M/25K, DeepSeek + GLM standard-drift only 1.26M/63K) | >=3.4M/0.09M | $0.40 est | $1.82 |
| 12 | 08-09 | Round 3: 10 content calls (5 fabric pieces + 5 oblique S1 email re-authors, deepseek-v4-flash-0731, 944p/776c measured for the re-author batch) | ~2K/2K | $0.01 | $1.83 |
| 13 | 08-09 | Round 3 probes: Luna standard-drift x1 (152K/1.9K) + Luna operative-deadline x1 (611K/3.1K) | 763K/5K | $0.08 | $1.91 |

Round-3 budget usage: 10 of 40 permitted content calls, 2 of 8 permitted
eval episodes. Entry 11 is the prior session's round-2 diagnosis matrix,
reconstructed from surviving eval2-*.log files; its DeepSeek and GLM runs
past standard-drift were not captured, so the row is an estimate rounded
up. Remaining: ~$23.09.

| 14 | 08-09 05:0x-05:4x | Eval matrix round 3 (post-epoch-fix, 5x3x3) | 17.6M/0.38M | $1.62 | ~$3.5 |

Round-3 matrix: standard-drift .75x3, fee-dispute 1.0x3, vanished-clause
.90x3, client-departure .85x3, operative-deadline 1.0/0.0/1.0. The epoch
fix un-suppressed date components; identical cross-model scores indicate
grader-structure ceilings, under component diagnosis in round 4.
Remaining: ~$21.5.

| 15 | 08-09 | Round-4 diagnosis probes: GLM x4 (operative-deadline 1.37M/12K, standard-drift 175K/16K, fee-dispute 87K/5K, vanished-clause 178K/4K) + DeepSeek x2 (client-departure 281K/13K, operative-deadline 2.79M/46K) | 4.89M/0.10M | $0.43 | ~$3.93 |
| 16 | 08-09 | Round-4 verification probes: operative-deadline + fee-dispute x 3 models x 1 attempt (DS 1.84M/29K, GLM 1.93M/29K, Luna 756K/6K) | 4.52M/0.06M | $0.40 | ~$4.33 |

Round-4 budget usage: 12 of 30 permitted eval-probe episodes, 0 of 30
permitted content calls (every record change was a code constant; the
content cache served all 57 pieces with zero LM calls). Verification
after the DEFECT fixes and hardening: fee-dispute 1.0/1.0/1.0 with the
extended per-entry deliverable; operative-deadline 1.0 (DeepSeek, 74
calls through the 1,680-message DM fabric), 0.0 (GLM, max_turns — read
each DM at limit 5, too shallow to reach the correction, wrote nothing),
0.3666 (Luna, reported the stale June 18 after never enumerating DMs —
the same strategy-variance failure its round-3 attempt 3 showed).
Remaining: ~$20.67.

| 17 | 08-09 | Round-5 content: 5 NDA bodies (deepseek-v4-flash-0731, ~0.7K/3.4K est from cached word counts; the build's usage line was consumed by a pipe) | ~0.7K/3.4K | $0.01 | ~$20.66 |

| 18 | 08-09 07:2x-08:3x | Eval matrix round 4 (final, 5x3x3) | ~29M/0.4M | $2.87 | ~$7.0 |

Final. See REPORT.md for the matrix, verdict, and remaining-budget plan.

| 19 | 08-09 | Round-6 record build (reconciliation fabric, all code constants; content cache served every piece) | 0 | $0.00 | ~$7.0 |
| 20 | 08-09 | Round-6 probes under the entry-17 call budgets: fee-dispute x Luna x2 (1.02M/9.4K, $0.108) + standard-drift (234K/4.3K, $0.026) + vanished-clause (448K/5.3K, $0.048) + client-departure (120K/2.2K, $0.013) + operative-deadline (156K/2.6K, $0.017), all openai/gpt-5.6-luna | 1.98M/23.8K | $0.21 | ~$7.2 |

Round-6 budget usage: 6 of 20 permitted probe episodes, 0 of 20 permitted
content calls. Floors measured by datasets/hartwell/measure_floors.py
(scripted client on the real MCP servers, each sequence asserting it
reproduces ground truth): client-departure 11, fee-dispute 33,
operative-deadline 40, standard-drift 48, vanished-clause 110; caps at 3x
= 33/99/120/144/330 in task.toml [harness] max_tool_calls. Probe scores
(best-of-N, stop reasons): fee-dispute 0.93 (0.44 finish / 0.93 finish —
attempt 2 ran the full support audit, 12 DM window reads plus per-day
windowed marker searches, in 49 of 99 calls); standard-drift 1.00 (finish,
55 calls — Luna executed the reference version-walk almost exactly);
vanished-clause 0.70 (finish, 82 calls — exact clean list and drop, but
four extra ids in unreviewed_revisions zeroed the 0.30 component);
client-departure 0.00 (call_budget at 33 — burned the cap on broad
searches and reaction reads, never wrote the deliverable; first live
enforcement of the entry-17 budget); operative-deadline 0.17 (finish, 32
calls — reported the stale June 18 again, never opened a DM, partial
stale list zeroed at all-or-nothing). Under the declared a-priori policy
2 of 5 probed cells fall below 0.5; the strongest model clears the other
three by executing reference-quality paths within task-anchored budgets.
Remaining: ~$17.8.

| 21 | 08-09 09:3x-11:3x | Eval matrix round 5 (call-budgeted, 5x3x3) | ~33M/0.5M | $3.94 | ~$11.4 |

Round-5 matrix: fee-dispute .00/.00/.44 and client-departure .00/.00/.44
DEFEAT ALL THREE; vanished-clause blocked by Luna (.70), operative-deadline
by DeepSeek (1.0), standard-drift by DeepSeek+Luna (1.0). Three new
reconciliation-shape tasks being mined to close the >=5 gap. ~$13.6 left.

| 22 | 08-09 12:xx-14:xx | Round-7 mining: three tasks finished from the existing world log (zero content calls; every ground truth is a query over the built bundle) | 0 | $0.00 | ~$11.4 |
| 23 | 08-09 | Round-7 probes, 6 episodes: Luna x response-latency x2 (1.69M/10.5K), Luna x second-read (825K/9.3K), Luna x billing-hygiene (3.43M/8.5K), Luna x visitor-log (809K/10.5K), DeepSeek x billing-hygiene (10.98M/42.9K) | 17.7M/81.6K | $9.62 | ~$1.8 |

Round-7 budget usage: 6 of 12 permitted probe episodes, 0 of the
permitted content calls. The $9.62 is the token x list-price **upper
bound** (Luna $8.84, DeepSeek $0.78) and is the figure that must be
reconciled against metered credits before it is believed — the failure
log's item 8 records that this arithmetic has overstated spend before,
and round 6's metered Luna probes came in near a tenth of their list
estimate. Two runs dominate the count: DeepSeek's billing-hygiene episode
resent a very large context for 30 turns (11.0M prompt tokens on its own),
and Luna's billing-hygiene sweep 3.4M.

Probe scores (best-of-1, stop reasons): billing-hygiene 0.13 Luna
(finish, 104/255 calls) and 0.00 DeepSeek (max_turns, 84/255);
second-read 0.11 Luna (finish, 61/159); visitor-log 0.11 Luna (finish,
74/159). Retired before shipping: response-latency, 0.88 Luna both before
and after hardening (finish, 31 then 32 of 36 calls) — its floor is 12
because both sides of its join sit on searchable surfaces. Floors
measured by measure_floors.py: billing-hygiene 85, second-read 53,
visitor-log 53; caps 255/159/159.

## Metered reconciliation (authoritative)

Token x list-price arithmetic overstates this run badly — episodes resend a
large stable prompt every turn and OpenRouter bills cached reads at a
fraction of list. Measured against the credits endpoint:

| point | metered credits used | session spend |
|---|---|---|
| session baseline | 32.2139 | 0 |
| after round-5 matrix | 39.8779 | $7.66 |
| after round-7 mining probes | 40.4330 | **$8.22** |

Round 7's six probe episodes cost **$0.55**, not the $9.62 list-price upper
bound recorded in entry 23. All list-price rows above are upper bounds;
these three readings are the truth. **Remaining against the $25 cap:
$16.78.**
