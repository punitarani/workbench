# Build spec: porting the pass^k agentic compliance suite into the Hartwell env

Status: recipe validated (see FAILURE-MODES-FRONTIER.md → "RESOLVED: the agentic
recipe"). Foundation landed (`connect_readwrite` in `tools/.../db.py`). This spec
is the concrete, code-grounded plan for the remaining integration, so it can be
built in a focused session without re-deriving the design.

## Goal

An outcome-graded agentic benchmark where a frontier model completes an intricate
legal new-matter *intake compliance* workflow against the real firm world, graded
on the **final world-state**, scored at **pass^k**. Measured recipe: per-attempt
≈ 0.99^(#intricate invariants); ~13 invariants → 0.87 (pass⁵ = 0.50); a queue of
2–3 matters (~30–40 invariants) → ~0.6–0.7 → pass²⁻³ ≤ 0.5. Legitimate: the
workflow's native success criterion is "did you complete a compliant intake,"
grading is final-state (un-gameable), the mechanical floor passes every invariant
(expert-solvable), and pass^k is τ-bench's standard reliability metric — NOT the
analysis-task partial-credit→certified metric swap that was rejected.

## The validated invariant set (from the in-memory probes)

Each is a discover-or-elicit condition where Opus genuinely slips ~1–10%:
1. Affiliate conflict via a differently-named parent → `conflict_pending` + wall + notice.
2. Positional conflict (position for this client contradicts one held for another current client).
3. Foreign-ownership (>25%) → OFAC check + enhanced-KYC.
4. Contingency vs. cost-advance (elicited from the partner's self-contradiction): fee retainer ≠ cost advance.
5. Third-party litigation funder → conflict-check the funder + flag + disclose in letter.
6. Contractual limitations period overriding the statutory default (read the contract).
7. Rule 1.18 prospective-client screen (adverse party previously consulted the firm).
8. Lateral-hire imputation screen (a recent lateral worked the other side).
9. Engagement letter sent; trust discipline (no unearned transfer); improper emergency-TRO demand declined.

## Architecture

### 1. A `compliance` ToolSystem (`tools/src/tools/compliance/`)
Follows the `ToolSystem` contract (framework.py) with one deviation: it is
**scenario-seeded**, not world-log-projected. Two table families:
- **Reference tables** (read-only to the agent), seeded from the scenario fixture:
  `firm_positions`, `prospective_clients`, `laterals`, `advance_waivers`,
  `entity_ownership`. These hold the discoverable traps that don't fit the
  existing Clio/Gmail/etc. surfaces.
- **Action tables** (agent-written via `connect_readwrite`): `intake_matters`,
  `compliance_flags` (kind ∈ positional|rule_1_18|imputation|enhanced_kyc|
  third_party_payor|contingency_writing|declined_request), `trust_entries`
  (kind ∈ fee_retainer|cost_advance|transfer), `intake_calendar`, `intake_letters`.

Read tools: `check_firm_positions`, `check_prospective_clients`, `check_laterals`,
`entity_lookup` (ownership + corporate family). Write tools mirror the probe:
`open_matter`, `flag_positional_conflict`, `flag_1_18_screen`,
`flag_imputation_screen`, `run_ofac_check`, `flag_enhanced_kyc`,
`record_trust_deposit`, `record_cost_deposit`, `flag_contingency_writing_required`,
`flag_third_party_payor`, `add_calendar_deadline`, `create_ethical_wall`,
`send_engagement_letter`, `send_conflict_notice`, `record_declined_request`.
Write tools open the DB with `connect_readwrite` and `INSERT`/`UPDATE` + `commit`.
Conflict *discovery* still uses the real read-only Clio surface (list_matters etc.)
so the affiliate/current-client conflicts are grounded in the real firm world.

### 2. Scenario seeding
Deviation from world-log projection: add a `seed(fixture: Path, conn)` alongside
`project`, and a task-build step that calls `create_db(compliance.db, tables)` then
seeds reference tables from `bundle/scenario.json`. Keep `handled_tags =
("person.record",)` and an empty/no-op `project` so the contract's people/meta
tables still populate from the world log (the agent's seat + directory work).

### 3. Aperture (`datasets/hartwell/harbor_stage.py`)
The generated `install.sh` moves state DBs to `/home/environment/state` (0700/0600,
environment-owned) and asserts the agent user cannot read them. The compliance
server runs as the `environment` user (setuid `run-as-environment`), so grant it
**rw** on `compliance.db` only: keep file mode 0600 owned by environment (already
rw for that user), and route the compliance server through `connect_readwrite`.
The agent still cannot touch the file directly — the boundary model survives; only
the `mode=ro` assumption changes for this one server's own DB.

### 4. State-diff grading criterion (`datasets/hartwell/tasks/<task>/tests/`)
A Reward Kit criterion that opens `WORKBENCH_STATE/compliance.db` (the verifier
already receives `WORKBENCH_STATE`, see `adapters/.../harness/grade.py`) and checks
each invariant as an independent boolean post-condition against the expected
end-state (computed by a `solution/solve.py`-style oracle from the scenario, the
same pattern as the existing tasks). Headline metric = **conjunctive pass**
(all invariants true) → the pass^k unit. Report per-invariant coverage alongside
for diagnostics. `measure_floors.py` gains a floor that reproduces the full
expected end-state through the tools (proves expert-solvability).

### 5. pass^k runner + measurement
Extend the Harbor matrix runner (or a small script) to run k independent rollouts
per scenario and report pass^k = fraction where all k certify. Target Opus pass²⁻³
≤ 0.5 on the queue-stacked scenario; also measure a sub-frontier model for
discrimination.

### 6. Anti-reward-hacking audit
- Expected end-state is NOT in the agent's inputs (derivable only by doing the work).
- Grade final state AND trajectory gates (e.g., conflict search precedes open;
  no substantive-work tool call while conflict_pending) so a right-state/wrong-path
  shortcut fails — the τ-bench conjunction.
- Confirm each invariant's failures are *substantive* (a real slipped step), not
  formatting brittleness: inspect the field-level diff of failing rollouts (the
  in-memory probes already showed genuine slips: missed positional inference,
  forgotten letter, cost-advance booked as retainer).

## Build order (each step verifiable)
1. ✅ `connect_readwrite` (landed).
2. `compliance` tables.py + a unit test (create → write via tool fn → read back).
3. `compliance` server.py (read + write tools) + `ToolSystem` + register test.
4. Scenario fixture (scenario.json) + seed step + one task bundle wiring the
   compliance server + the read-only Clio/Gmail servers via mcp.json.
5. State-diff grading criterion + expected-end-state oracle + `measure_floors` floor.
6. harbor_stage aperture change for compliance.db.
7. pass^k runner; measure Opus (target pass²⁻³ ≤ 0.5) + a sub-frontier model.
8. Author the queue-stacked (2–3 matter) scenario for the ≤0.5 headline; diversify
   to ~5 scenarios; anti-brittleness audit.

## Risks / open items
- The single-scenario per-attempt (0.87) has a wide CI at n=15; the queue-stack
  design reduces reliance on it, but confirm with a robust sample.
- Keep the reference-table traps realistic and each individually expert-obvious so
  the *only* difficulty is completeness/inference under load — not obscurity.
