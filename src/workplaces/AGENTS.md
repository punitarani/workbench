# Working in workplaces

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Workplace-specific:

* Everything here is **data**: `WorkplaceSpec` values, prose in
  `seed_docs/*.md` package files, recorded cassettes. Logic belongs in the
  engine; if a workplace needs code beyond assembling its spec, the engine
  is missing a seam — fix it there.
* Cast design carries the scenario. Personalities, channel registers,
  relationships, and `share_policy`-guarded knowledge are what make a
  recorded day worth training on; write them like characters, not like
  config.
* Editing anything that reaches a prompt (personas, seed docs, day script)
  invalidates the workplace's recorded cassettes. Re-record, re-run the
  acceptance suite, and commit spec + cassette together.
* Structural invariants (e.g. which phrases must not appear in seed
  content) are enforced by the workplace's test suite — run it before and
  after content edits. See [`legal/`](src/workplaces/legal/AGENTS.md).
