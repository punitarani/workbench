# datasets

Harbor tasks, grouped into datasets — the eval/RL deliverable built on top
of recorded workplace days. Arrives with Phase 3 of the
[v1 design](../docs/superpowers/specs/2026-08-08-workbench-v1-design.md):
tasks are mined from simulated history, ground truth extracted from
offstage state, every task validated (solvable, discriminating,
deterministic, leak-free) before it lands here.

Task format: `datasets/<dataset>/tasks/<task>/` per Harbor's layout
(`task.toml`, `instruction.md`, `solution/solve.sh`, `tests/test.sh`).

First task: **`legal-nda/tasks/vantage-triage/`** — reconstruct the
clause-by-clause triage memo for the Vantage vendor NDA from the day's
record. The vendor-standard clauses (mutual, two-year cap, no non-solicit)
exist only in Daniel's redline and email, never in the playbook, so a
playbook-only agent provably scores less (0.48 vs 1.0). Workspaces are
derived data and stay local; build one from a recorded day with
`uv run python datasets/legal-nda/build_task.py`.
