# workplaces

Concrete organizations, expressed as data against the engine's
`WorkplaceSpec`: the cast (persona parameters, institutional knowledge,
relationships), channels, seed documents, the day script of outside
arrivals, and the recorded cassettes that make a simulated day replayable.

This is the only layer that knows any domain. A new vertical — an
accounting close, a consulting engagement — is a new package here, not a
change to the engine.

Current workplaces:

* **`legal/`** — the Argent Systems legal department (Phase 1 demo): six
  people, an inbound vendor NDA, and an unwritten standard that lives only
  in one persona's head. Its acceptance suite proves the knowledge flowed
  person → conversation → artifact during the simulated day.

Record and replay a day with `python -m workbench.simulation.demo`; the
full workflow is in [`docs/simulation-engine.md`](../docs/simulation-engine.md).
