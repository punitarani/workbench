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
[`fidelity/`](fidelity/) — dated, frozen evidence. History.

> The split between the second and third exists because it once did not.
> Findings that generalized — measured, correct, expensive — were filed
> as run records, which this tree labels history and the next build did
> not read. They were re-derived a week later on another dataset at the
> cost of eight discarded experiments. **A finding that generalizes is
> not a run record.** If a measurement changes how the *next* environment
> should be built, it belongs in `METHOD.md`.

Measurement records, linked from WORKBENCH.md's appendices:

* [`fidelity/`](fidelity/) — [`bands.json`](fidelity/bands.json) (91
  committed bands, read by `analysis.fidelity`), the generated ledgers
  measured against them, and the CI-checked
  [`PARITY-MATRIX.md`](fidelity/PARITY-MATRIX.md).
* [`runs/`](runs/) — dated records of specific runs and evaluations.
  Reports and analyses only: raw rollout artifacts belong in the
  gitignored `jobs/`, and plans, checkpoints and migration notes do not
  belong in the tree at all.

`METHOD.md` also ships as a plugin. [`plugins/rl-env-factory`](../plugins)
packages it as six loadable skills, with every dataset, vendor and model
name stripped, so the method travels to the next environment without the
record of this one. The skills are the operational extract; `METHOD.md`
carries the reasoning at length. When they disagree, the skills are wrong.

Contributor and agent working rules live in the root
[`AGENTS.md`](../AGENTS.md) and in per-package `AGENTS.md` files.
