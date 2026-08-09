# Final report — four-month history run (2026-08-09)

## What was built (all committed, all reproducible from seed)

1. **Product-realistic tool surface**: gmail/slack/imanage/clio
   subpackages mirroring the official MCP servers (Gmail, Slack, iManage)
   and Clio Manage v4 (no official MCP exists in that category), on the
   plugin framework with all invariants (read-only, declared tags,
   sim.* exclusion, leakage, declarative coherence) and seat scoping.
2. **The Hartwell & Marsh history**: 87 workdays (2026-03-02→06-30),
   12 employees, 20 organizations, 14 externals, five multi-month
   storylines, ~4,000–4,400 events depending on round, byte-reproducible
   from seed + content cache; documents materialize as real files.
3. **The eval harness** (`adapters/`): MCP-workspace agent loop with
   OpenAI-format tool calling, per-attempt grading, transcripts.
4. **Five Harbor tasks** whose solve.sh earns 1.0 deterministically with
   naive baselines 0.21–0.38 (gap > 0.4 everywhere), each requiring
   cross-tool or cross-version joins.

## Task × model matrix (final, defect-free environment, best-of-3)

| task | DeepSeek V4 Flash | GLM 5.2 | GPT-5.6 Luna |
|---|---|---|---|
| standard-drift | 1.00 | 1.00 | 0.96 |
| fee-dispute-reconstruction | **0.00** | **0.00** | 0.70 |
| vanished-clause | 1.00 | 1.00 | 1.00 |
| client-departure-postmortem | 1.00 | 1.00 | 1.00 |
| operative-deadline | 1.00 | 1.00 | 1.00 |

**The ≥5-tasks-defeat-all-three bar was not met.** Two cells hold
(fee-dispute vs DeepSeek and GLM — the exhaustive orphan-entry
reconciliation); every other cell cleared 0.5.

## Why — the run's central finding

Across four eval rounds, apparent task difficulty was repeatedly
**environment defect, not model failure**. Three defects found by
transcript-driven diagnosis, each un-suppressing scores when fixed:

1. Served dates shifted +10 days (hardcoded epoch) — fixed by
   projecting the record's epoch into a meta table.
2. iManage never served the `path` column — models could not answer
   path components all three uniformly missed.
3. The harness's write_file corrupted structured JSON — GLM's correct
   answers graded 0.0.

Trajectory of the bar as defects fell: round 1 (2 defects live):
5/15 cells < 0.5. Round 3 (epoch fixed): 3/15. Round 4 (all fixed):
2/15 — while honest hardening (DM burial in a 1,680-message fabric,
9-NDA attestations, clean-document enumeration, exact-id components)
raised the *cost* of solving without lowering solve rates: models
parallelize tool calls, so the 30-turn budget admits hundreds of calls
and exhaustive walks fit. In a fair environment at this corpus scale,
2026 frontier-adjacent models solve retrieval-hard workplace tasks
under best-of-3.

## Spend ledger (cap $25)

GEPA + persona work $0.29 · generation $0.01 · eval rounds 1–4
$1.13 + $1.62 + $0.83 + $2.87 + probes ≈ **$7.0 total, ~$18 remaining**.
Per-row detail in LEDGER.md.

## What more budget buys (in priority order)

1. **A-priori call-budget policy** (~$0): set per-episode tool-call and
   token ceilings from a realistic cost model *before* any eval — the
   single strongest fair lever against parallel-call exhaustive walks.
   Must be declared before measurement, not tuned against it (declared
   after observing results, it is goodharting; that is why it was not
   applied tonight).
2. **10× corpus** (~$5–10 gen, ~$3/matrix): 2–3 firm-years, 100+
   multi-version documents, 10k+ DM messages — puts exhaustive walks
   beyond any plausible call budget while staying fully observable.
3. **Reasoning-hard shapes** (~$5): tasks where the join is cheap but
   the inference is hard — contradiction weighing across authorities,
   privilege-aware redaction decisions, counterfactual billing
   reconstructions — graded against offstage ground truth the record
   never states.
4. **Engine-recorded interactive days** + the externalized seat for
   ask-a-colleague tasks (persona replay backends exist; ~$2/day).

## Deliverable locations

DECISIONS.md (16 entries) · LEDGER.md (17 rows) · PLAN-phase2.md ·
datasets/hartwell/tasks/* · adapters/ harness · this report.
