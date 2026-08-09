# The grounded game master

* **Deterministic in v1: the GM makes zero LM calls.** Reference
  resolution, validation, routing, and timeflow are code. LM-backed repair
  (`RepairIntent`, `ResolveFreeform`) are named optimization-phase targets —
  do not add model calls here casually; they multiply cassette size and
  nondeterminism surface.
* Coherence is structural: a reference either resolves against `WorldState`
  or the intent is rejected into a visible `sim.gm.note` (never an
  exception that kills the run, never a silent drop, never an invented
  entity).
* The GM sees every event through `route()`: world state and the id minter
  absorb there. New id-bearing payloads must reach `_absorb_id`, or minted
  ids will collide with scripted ones.
* Turn-granting (`next_acting`) is where day dynamics live. Current
  dampeners exist for a reason: reply chains stop auto-granting at depth 3
  (courtesy-loop prevention — attempt 4 produced 200+ acknowledgment
  emails), and wakes route to their own persona so its clock advances.
  Tune dynamics here, not by weakening validation.
* `timeflow.intent_duration` is a pure function; keep it free of state and
  randomness.
