# docs

[`WORKBENCH.md`](WORKBENCH.md) is the single source of truth: mission,
as-built architecture, worlds, measured numbers, commands, and known
gaps. Start and end there.

Everything else in this tree is a measurement record, kept as evidence
and linked from WORKBENCH.md's appendices:

* [`epochs/v2/`](epochs/v2/) — the committed distribution bands
  (`bands.json`, read by tests), the generated fidelity ledgers, and the
  CI-checked [`PARITY-MATRIX.md`](epochs/v2/PARITY-MATRIX.md).
* [`runs/`](runs/) — dated, frozen records of specific runs and
  evaluations. History, not guidance.

Contributor and agent working rules live in the root
[`AGENTS.md`](../AGENTS.md) and in per-package `AGENTS.md` files.
