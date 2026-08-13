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
| `tests/scenario.json` | seed for the compliance reference tables (the discoverable traps); `bundle/` is derived/gitignored, so the seed is committed under `tests/` |
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

## Container integration — wired (needs one real Harbor run to certify)

The three harness pieces the read-only tasks never required are now in place and
unit-tested for *generation*:

1. **Serve** — `serve compliance` resolves (`tools/src/workbench/tools/serve.py`);
   the system is kept out of the global `REGISTRY` (it would auto-materialize +
   expose writes in every task) and served opt-in. `build_tasks` generates
   `bundle/mcp.json`.
2. **Aperture** — none needed. The staged state DBs are env-owned `0600`, so the
   env-user compliance server opens `compliance.db` read-write while the agent
   still reaches it only through the (write) MCP surface. `harbor_stage.py` now
   derives the served tool set per bundle, adding `compliance` (its wrapper + the
   `serve` allowlist entry) when `compliance.db` is staged — the read-only tasks
   are unchanged.
3. **`build_tasks.py`** — `build_compliance_task()` creates + seeds
   `bundle/state/compliance.db` from `tests/scenario.json` and stages the bundle.

Build it: `uv run python datasets/hartwell/build_tasks.py --tasks
matter-intake-compliance`. What is **not** yet certified is the in-container
execution of `install.sh` under the setuid boundary (env-user read-write on
`compliance.db`, the agent-cannot-touch assertions) — that needs one real Harbor
run, which can't be reproduced on the host. Until then, the harness in
`docs/runs/2026-08-09-four-month-history/` drives the real compliance server + this
verifier directly.
