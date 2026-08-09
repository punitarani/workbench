# datasets

Harbor tasks, grouped into datasets — the eval/RL deliverable built on top
of recorded workplace days. Arrives with Phase 3 of the
[v1 design](../docs/superpowers/specs/2026-08-08-workbench-v1-design.md):
tasks are mined from simulated history, ground truth extracted from
offstage state, every task validated (solvable, discriminating,
deterministic, leak-free) before it lands here.

Empty until then. Task format: `datasets/<dataset>/tasks/<task>/` per
Harbor's layout (`task.toml`, `instruction.md`, `solution/solve.sh`,
`tests/test.sh`).
