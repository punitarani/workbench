# docs

Three kinds of document, and the distinction matters:

**What the system is.** [`WORKBENCH.md`](WORKBENCH.md) — mission,
as-built architecture, worlds, measured numbers, commands, known gaps.
The single source of truth for the thing that exists.

**How to build and measure well.** [`METHOD.md`](METHOD.md) — the rules
for building a world, cutting tasks from it, measuring models against
them, and knowing that what you measured was the model. Domain- and
dataset-independent. Extend it whenever a measurement teaches something
that will hold on the next dataset.

**What happened on a particular day.** [`runs/`](runs/) and
[`epochs/v2/`](epochs/v2/) — dated, frozen evidence. History.

> The split between the second and third exists because it once did not.
> Findings that generalized — measured, correct, expensive — were filed
> as run records, which this tree labels history and the next build did
> not read. They were re-derived a week later on another dataset at the
> cost of eight discarded experiments. **A finding that generalizes is
> not a run record.** If a measurement changes how the *next* environment
> should be built, it belongs in `METHOD.md`.

Measurement records, linked from WORKBENCH.md's appendices:

* [`epochs/v2/`](epochs/v2/) — committed distribution bands
  (`bands.json`, read by tests), generated fidelity ledgers, and the
  CI-checked [`PARITY-MATRIX.md`](epochs/v2/PARITY-MATRIX.md).
* [`runs/`](runs/) — dated records of specific runs and evaluations.

Contributor and agent working rules live in the root
[`AGENTS.md`](../AGENTS.md) and in per-package `AGENTS.md` files.
