# Working in ashgrove

Root rules in [`../../AGENTS.md`](../../AGENTS.md) and dataset rules in
[`../AGENTS.md`](../AGENTS.md) apply.
[`../../docs/METHOD.md`](../../docs/METHOD.md) is the method these
scripts implement; [`DIFFICULTY.md`](DIFFICULTY.md) and
[`LEDGER.md`](LEDGER.md) are this world's measured evidence.

## The pipeline, in the order it must run

| script | what it does | refuses when |
|---|---|---|
| `run_epoch.py` | records or replays the world | audit gates fail |
| `build_tasks.py` | materializes the bundle, runs every reference solver, stages each task | a solver no longer reproduces its committed oracle, or an oracle names a value no tool serves |
| `verify_oracle.py` | re-derives every answer from raw events | a derivation disagrees with the committed oracle |
| `run_rollouts.py` | k trials per task per model, per-criterion aggregation | — |
| [`scripts/band.py`](../../scripts/band.py) | the multi-model mean, over gradeable trials only | fewer than two gradeable trials for any model |
| `classify_misses.py` | E/T/M evidence for every criterion below 1.0 | — |
| `adjudicate.py` | prints the source sentence behind a disputed row | — |

`pipeline.py` chains audit → build → verify → rollouts → classify, and
each stage can refuse.

## Invariants these scripts encode

* **`build_tasks.py` clears `workspace/` and `state/` before
  materializing.** The materializer only writes; without the clear, a
  directory accumulates every world ever built there and nothing notices
  until a task grades those files.
* **`--refresh-truth` reads the world from the bundle's `SOURCE` file**,
  never from a fixed default. A fresh answer key derived from a stale
  world is invisible to every other check.
* **`verify_oracle.py` derives from `analysis.world_facts`** —
  raw events, no projection code. Where a value is minted by the
  projection (a chat timestamp, a rendered file path) it is compared as a
  multiset of facts rather than restated, because restating it would copy
  the code under test.
* **`scripts/band.py` never averages a non-answer as a zero**, requires two
  gradeable trials before reporting a mean, and prints the completion
  rate beside the verdict rather than folding it in.
* **`classify_misses.py` reads the deliverable the grader reads**, not
  the first JSON in the directory — agents leave working files behind —
  and compares rows dropped by *every* trial rather than the worst
  pairwise overlap.
* **`adjudicate.py`'s net is asserted a strict superset of each rule**,
  over the corpus rather than over examples. It exists so a verdict is
  read off the source sentence instead of off the regex that produced the
  row.

## Before trusting any of them

Each of these tools has had a bug that produced a false verdict. Check a
new signal against a hand computation before acting on it; running the
tool again only reproduces its own error.
