# workplaces

Concrete organizations, expressed as data against the engine's
`WorkplaceSpec`: the cast (persona parameters, institutional knowledge,
relationships), channels, seed documents, the client book and season,
and any recorded cassettes that make a simulated span replayable.

This is the only layer that knows any domain. A new vertical is a new
package here, not a change to the engine.

Current workplaces:

* **`legal/`** — the Argent Systems legal department, the original
  single-day demo: six people, an inbound vendor NDA, and an unwritten
  standard that lives only in one persona's head. Its acceptance suite
  (active when a local cassette is recorded) proves the knowledge flowed
  person → conversation → artifact during the simulated day.
* **`hartwell/`** — Hartwell, the frozen v1 litigation firm: genesis,
  cast, voice, and storylines behind the deterministic four-month
  chronicle that `datasets/hartwell/build_history.py` builds and the
  ten-task Harbor suite reads.
* **`calder/`** — Calder & Finch, CPAs: a 17-person tax-led firm with an
  epoch spec, season model, and arcs. `cassettes/` carries the committed
  two-day acceptance recording (replayed byte-identically in CI) and the
  five-day flagship week; the full six-month epoch cassette stays local.
* **`ashgrove/`** — Ashgrove Reid LLP, the comparison firm: exactly
  Calder's seventeen professionals (the controlled variable) working an
  assurance-led book on a different calendar, on the v2 engine with
  timesheets and a rate sheet.

Epochs run through `datasets/<world>/run_epoch.py`; the single-day legal
demo through `python -m simulation.demo`. Architecture and the
record/replay workflow are in
[`docs/WORKBENCH.md`](../../../docs/WORKBENCH.md).
