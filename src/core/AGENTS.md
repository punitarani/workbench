# Working in workbench (core, environment)

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Package-specific:

* **Environment never imports simulation or workplaces.** It sees the world
  only through core events; the world log is its sole input. The tool
  surface it assembles lives in the [`tools/`](../tools/) member.
* **Materialization gates on validation**: an incoherent log never becomes
  an environment.
* **The bundle root is not the agent's workspace.** `materialize` writes
  `state/`, `mcp.json`, and `environment.toml` beside `workspace/`, never
  inside it: the agent inhabits `workspace/` alone, and everything that
  serves it stays a directory above. Anything new that materialization
  emits chooses a side of that line deliberately.

Core-specific:

* **Everything here is a contract.** Simulation, workplaces, and the tool
  servers all deserialize what core serializes. A change to any model's
  fields or serialization invalidates recorded world logs and cassettes —
  the golden-log test will fail; regenerate deliberately and say so in the
  commit message.
* **Domain-neutral, layer-neutral.** No legal/finance/consulting values, no
  imports from `simulation` or `workplaces`, no LM
  concepts. Field descriptions become model-visible prompt text downstream —
  keep them generic (a workplace name in a core description leaks into every
  workplace's prompts).
* Frozen Pydantic models, `extra="forbid"`, discriminated unions on `kind`.
  Validators enforce cross-field invariants at construction, not at use.
* Ids are minted (`IdMinter`) or derived (`event_id_for`), never random.
  Every source of randomness flows through `seed.derive_seed`.
* The event vocabulary has its own rules: see
  [`src/core/events/AGENTS.md`](src/core/events/AGENTS.md).
