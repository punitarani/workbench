# Decisions — four-month history run

Assumptions and judgment calls made while executing autonomously; each
entry says what was ambiguous and which reading was taken.

1. **Prior GEPA spend counts against the cap.** The goal's cap names GEPA;
   tonight's persona-optimization spend (~$0.23 est) predates the goal but
   is the same key and purpose, so it is in the ledger.
2. **Deliverable docs live under `docs/runs/2026-08-09-four-month-history/`**
   — the repo rule routes documentation to `docs/`; DECISIONS.md and
   LEDGER.md are documentation of this run.
3. **GEPA verdict: infrastructure and one structural fix shipped;
   instruction adoption deferred to the Phase 2 pilot.** The loop found
   and fixed a real grounding bug (personas could not see their chat
   channels — committed), and proved the shipped `decide` text never
   initiates chat (0.525 on 4/4 seeds). But no *generic* candidate passed
   both gates: the scenario winner (0.938 train / 0.900 delivery-metric
   holdout) produced a degenerate full day (3 emails, zero document
   revisions — narration-as-work); the delivery-aware rerun's winner
   quoted the evaluation day verbatim (reward hacking, mechanically
   banned thereafter); generic-forced mutations scored 0.300-0.600.
   Hand-merges failed twice (0.525, 0.400) — instruction efficacy is
   phrasing-order sensitive, so only measured text ships. The original
   instruction is restored; the goal's own structure (new 12-person firm,
   new tool schemas, pilot-then-GEPA) makes further tuning against the
   6-person org wasted spend. Evidence: out/gepa-run{1..4}, holdouts.
4. **Deferred wake-time semantics**: recorded days keep intra-day
   scheduling; the chronicle will offset compiled times per day and
   thread minter state by scanning the log (no engine changes).
