# Working in workbench.simulation

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Engine-specific:

* **Determinism is the product.** Same seed, same bytes — across processes
  and PYTHONHASHSEED values. Anything ordered must be ordered explicitly
  (declaration order, sorted tuples, `(time, order)` keys); anything random
  derives from `workbench.core.seed`; anything from a model goes through the
  cassette. If you cannot say why your change is deterministic, it isn't.
* **Failures are loud.** No silent degradation anywhere: budget exhaustion,
  cassette misses, snapshot drift, transport failures all raise typed errors
  from `errors.py`. Never return an empty string, a default, or a truncated
  result in place of an error.
* **Prompt-affecting changes invalidate cassettes.** Signature docstrings,
  field descriptions, rendering, request parameters — all of it keys the
  cassette. Expect to re-record the demo day and say so in the commit.
* Recorded-day failures are diagnosed from the world log (`sim.gm.note`
  events) and reproduced offline by replaying the cassette. Fix with a
  failing unit test first; the live model is only for recording, never for
  debugging logic.
* Subfolder rules: [`lm/`](src/workbench/simulation/lm/AGENTS.md),
  [`engine/`](src/workbench/simulation/engine/AGENTS.md),
  [`gm/`](src/workbench/simulation/gm/AGENTS.md),
  [`persona/`](src/workbench/simulation/persona/AGENTS.md).
