# matter-intake-compliance

The first **write-workflow** task in the Hartwell suite. The agent completes a
new-matter intake by **mutating firm state** through the compliance tool surface,
and grading reads the resulting world-state — not a deliverable file. It is
outcome-graded (pass^k), un-gameable (an agent that narrates the right answer
without writing it to the record scores zero), and expert-solvable (the reference
solution's tool-path certifies).

## Layout

| Path | Role |
|---|---|
| `task.toml` | task manifest |
| `instruction.md` | the intake manual + the matter |
| `bundle/scenario.json` | seed for the compliance reference tables (the discoverable traps) |
| `tests/expected.json` | the expected end-state (required actions, forbidden action) |
| `tests/criteria.py` | the verifier — reads `WORKBENCH_STATE/compliance.db` action tables, conjunctive outcome + coverage |
| `solution/solve.py` | reference solution / expert floor — issues the correct tool calls; the verifier certifies it |
| `test_intake_compliance.py` | 9 tests: correct certifies, each defect flips its check, the oracle floor certifies |

## What it grades (13 outcome checks, conjunctive)

Matter opened `conflict_pending` (affiliate conflict, waiver is transactional-only
so it does not clear a litigation matter); `positional` / `rule_1_18` /
`imputation` / `ethical_wall` / `conflict_notice` flags with the right subjects;
`enhanced_kyc` + `ofac_check` (client is 40% foreign-owned); the retainer booked
to trust as `fee_retainer`; **no** `transfer_to_operating`; the **contractual
2-year** limitations deadline (2026-02-10, not the statutory 4-year); the
engagement letter sent.

## Measured difficulty

Outcome-graded, measured on the raw `/chat/completions` harness (see
`docs/runs/2026-08-09-four-month-history/FAILURE-MODES-FRONTIER.md`): the single
intake is high-variance and dominated by the **positional inference** — GPT-5.6
Sol ≈ 0.16–0.40, Opus 5 ≈ 0.63–1.0 depending on how much is elicited vs. stated.
The **reliable ≤0.5** form is the **2-matter queue** (this task ×2 with distinct
entities, all-or-nothing): pass² ≈ 0.40–0.46 for Opus, ≈ 0.02 for Sol. Honest
caveat recorded in the failure-mode doc: manufacturing a *single*-task ≤0.5 for
Opus tends to produce grader artifacts, so this bundle's headline ≤0.5 claim is
the **compounded (queue) unit**, and Sol is the model it discriminates cleanly.

## Remaining container-integration (not yet wired; the read-only tasks don't need it)

This bundle's **verifier and oracle are complete and tested here**, but running it
end-to-end inside the Harbor container needs three harness pieces the read-only
audit tasks never required (scoped in
`docs/runs/2026-08-09-four-month-history/AGENTIC-PASSK-PORT-SPEC.md`):

1. **Serve the compliance system in the container** — `bundle/mcp.json` composing
   the `compliance` server; it is deliberately kept out of the global `REGISTRY`
   (it would auto-materialize + expose writes in every task), so it needs a
   task-scoped serve entry.
2. **A read-write aperture** for `compliance.db` in `datasets/hartwell/harbor_stage.py`
   — the compliance server runs as the `environment` user (setuid `run-as-environment`),
   so it can be granted `rw` on `compliance.db` only, leaving the agent unable to
   touch the file directly; the current `install.sh` asserts read-only.
3. **`build_tasks.py`** step that creates `bundle/state/compliance.db` from
   `SYSTEM.all_tables()` and seeds it from `bundle/scenario.json`.

Until those land, measure with the harness in `docs/runs/.../` (drives the real
compliance server + this verifier directly).
