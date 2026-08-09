# Working in workbench.core

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Core-specific:

* **Everything here is a contract.** Simulation, workplaces, and (later)
  tool servers all deserialize what core serializes. A change to any model's
  fields or serialization invalidates recorded world logs and cassettes —
  the golden-log test will fail; regenerate deliberately and say so in the
  commit message.
* **Domain-neutral, layer-neutral.** No legal/finance/consulting values, no
  imports from `workbench.simulation` or `workbench.workplaces`, no LM
  concepts. Field descriptions become model-visible prompt text downstream —
  keep them generic (a workplace name in a core description leaks into every
  workplace's prompts).
* Frozen Pydantic models, `extra="forbid"`, discriminated unions on `kind`.
  Validators enforce cross-field invariants at construction, not at use.
* Ids are minted (`IdMinter`) or derived (`event_id_for`), never random.
  Every source of randomness flows through `seed.derive_seed`.
* The event vocabulary has its own rules: see
  [`src/workbench/core/events/AGENTS.md`](src/workbench/core/events/AGENTS.md).
