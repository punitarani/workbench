# Checkpoint — resume state

Written so this run survives context loss. Update at every phase boundary.

## Current phase: re-derivation after the world regeneration

The record was regenerated for realism (444d128). Storyline beats and all
56 storyline audits survive; derived values did not. Two agents are
re-deriving ground truths — one on four id/count-drift tasks, one on four
whose answer sets went degenerate (72 items, 2 items) and need a rule
tightening that is harder, never easier.

**Until that lands the suite is NOT green**: fee-dispute skips behind a
coherence guard and the other hartwell tasks fail. The matrix recorded
below was measured against the PREVIOUS world and must be re-run.

## Where the goal stands

| Requirement | State |
|---|---|
| tools/ on official MCP surfaces, invariants passing | **done** (gmail/slack/imanage/clio; 4/8/9/8 tools) |
| 4-month history generated, materialized, coherence-clean | **done** (87 workdays, ~6.3K events, `--check` byte-identical) |
| ≥5 tasks, solve 1.0, all three models < 0.5 | **2 confirmed best-of-3, 3 more at best-of-1**; full matrix owed |
| suite green (sync/pytest/ruff) | **green** (393 tests, ruff check + format clean) |
| aspect-grouped commits, data gitignored | holding — round 7 is uncommitted on purpose |
| final report (ledger, matrix, open items) | REPORT.md exists, needs the 7-task matrix |

## The suite: seven tasks

| task | DeepSeek V4 Flash | GLM 5.2 | GPT-5.6 Luna | bar |
|---|---|---|---|---|
| fee-dispute-reconstruction | 0.00 | 0.00 | 0.44 | **met** (best-of-3) |
| client-departure-postmortem | 0.00 | 0.00 | 0.44 | **met** (best-of-3) |
| billing-hygiene-audit | 0.00 | — | 0.13 | met at best-of-1 |
| second-read-audit | — | — | 0.11 | met at best-of-1 |
| visitor-log-audit | — | — | 0.11 | met at best-of-1 |
| vanished-clause | 0.00 | 0.00 | 0.70 | Luna |
| operative-deadline | 1.00 | 0.17 | 0.17 | DeepSeek |
| standard-drift | 1.00 | 0.00 | 1.00 | DeepSeek+Luna |

Round-7 cells are single attempts. The three new tasks need GLM and
DeepSeek coverage and a best-of-3 rerun before any of them is claimed.

## Round 7: the three mined tasks are complete

All three build, solve 1.0, naive well under solve−0.4, floors measured,
caps in task.toml, task tests and the immersion lint green. No change of
any kind to the world record, and no content calls.

| task | core rule (weight 0.56, all-or-nothing) | answer set | floor / cap | solve / naive |
|---|---|---|---|---|
| billing-hygiene-audit | time entries whose timekeeper wrote nothing anywhere — mail, channel or **DM** — on the entry's date | 7 activity ids | 85 / 255 | 1.00 / 0.13 |
| second-read-audit | draft-review requests in one-to-one chat with nothing back from the person asked, by chat or mail, through the next working day | 4 Slack ts | 53 / 159 | 1.00 / 0.18 |
| visitor-log-audit | sign-in-sheet handover requests never closed under the same window rule | 6 Slack ts | 53 / 159 | 1.00 / 0.19 |

Two of the briefed veins were replaced, on measurement, not taste
(DECISIONS entry 21):

- **dm-disclosure is empty by construction.** The DM fabric is
  deliberately matter-blind (entry 15d); all ten client markers over all
  2,157 DM messages return two hits, both inside the relevant deal team.
  Replaced by second-read-audit.
- **response-latency is real but not defensible.** The join is clean (4
  late-answered messages against 103 never-answered decoys), but both
  sides sit on surfaces Gmail search returns, so the floor is 12 and Luna
  scored 0.88 — twice, before and after hardening the brief and recutting
  the core onto the dated exception report. Retired rather than shipped
  as a known-failing task. Replaced by visitor-log-audit.

The standing lesson: in this record, difficulty comes from the direct
messages chat search cannot reach. Any future vein whose anchor **and**
coverage are both searchable should be assumed Luna-solvable.

## Next actions, in order

1. Full matrix on the three new tasks (3 tasks x 3 models x 3 attempts).
2. Reconcile round-7 spend against metered credits; the $9.62 in LEDGER
   entry 23 is a token x list-price upper bound, not a reading.
3. Harden any cell ≥ 0.5; re-probe.
4. GEPA re-run on Luna (persona instructions were tuned against DeepSeek).
5. Final REPORT.md update with the seven-task matrix.
6. Commit round 7 (nothing from this round is committed).

## Spend

Metered credits stood at 39.88 of 70 granted before round 7 (session
baseline ~32.21, so ~$7.7 of the $25 cap spent then). Rounds 5-7 add an
estimated ~$13.6 of list-priced tokens; the honest number needs a metered
read, which this session could not take. Treat remaining budget as
uncertain and small until it is reconciled.

## Failure/fix log (for the final report)

1. Persona channel invisibility (couldn't see own chat channels) → situation
   block lists member channels — `542b06a`.
2. GEPA winner quoted the evaluation day verbatim (reward hacking) →
   mechanical banned-terms filter on proposals — `34fcbe6`.
3. Served dates +10 days off (hardcoded legal-day epoch in all four servers)
   → epoch travels in a per-database meta table — `19a0755`.
4. iManage never served the `path` column (models could not answer path
   components) → path in search hits/profiles/children — `19a0755`.
5. Harness `write_file` str()-coerced dict content → every grader's
   json.loads failed (GLM scored 0.0 on correct answers) → json.dumps —
   `19a0755`.
6. Cassette keys include the model, so changing DEFAULT_MODEL would miss
   every entry → replay pins its recorded model — `ffd385f`.
7. Mining agent terminated by a Fable 5 account limit → relaunched on Opus 5;
   the three tasks it left half-built are now finished (round 7).
8. Ledger overstated spend ~50% (token x list price ignores prompt caching)
   → reconcile against metered credits.
9. Instructions leaked eval scaffolding; tool databases sat inside the agent
   workspace → bundle split + immersive rewrite — entry 20.
10. The dead agent's billing-hygiene grader reads as broken — a bare
    `except TypeError, ValueError:` — but that is valid on the Python
    3.14 the Dockerfile pins (PEP 758), and ruff normalizes a
    parenthesized rewrite back to it. Not a bug; the missing pieces were
    structural (task.toml, test.sh, baseline, task test, floor).
11. A task whose anchor and coverage are both search-returnable cannot be
    made hard by writing (response-latency: 0.88 Luna before and after
    hardening) → retired, and the property is now a design rule.
