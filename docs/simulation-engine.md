# The simulation engine

`workbench.simulation` is a clean-room, typed, async, deterministic rebuild of
the generative agent-based modeling pattern DeepMind's Concordia introduced.
No Concordia code or dependency; the audit that led to rebuilding rather than
forking is summarized in the v1 design spec.

## Shape

```
workbench.core          events, intents, actions, world log, seeds, ids
workbench.simulation    engine, entities, personas, game master, LM layer
workbench.workplaces    concrete casts, seed documents, day scripts
```

One simulated day is a loop over scheduled drafts:

1. The engine pops the earliest `(time, order)` draft and mints it into a
   world event — seq is assigned at occurrence, so the log is gapless and
   time-ordered even for delayed events.
2. The game master routes it; attention masks defer what a busy person
   shouldn't see yet; observers fold it into their working memory.
3. The GM picks who acts. The actor's DSPy programs decide and draft; the
   result is a typed `ActionIntent`, never free text.
4. The GM grounds the intent against world state — names resolve or the
   intent is rejected into a visible `sim.gm.note`. Grounded intents become
   scheduled drafts with durations from the pure timeflow model.

Personas are grounded, not imaginative: their working memory is the observed
events themselves, so a character can only reference what actually happened.
Institutional knowledge (the unwritten standard) lives in persona params with
a sharing policy, and the audit litmus proves it flowed person → conversation
→ artifact during the day rather than leaking from a seed.

## Determinism

- One `Seed` enters at the run entry; everything derives via
  `derive_seed(seed, *path)` (blake2b, PYTHONHASHSEED-independent).
- Every LM request carries a derived seed and is keyed by content hash into
  the cassette store. Replay misses raise; budgets raise; nothing degrades
  silently.
- All fan-out is `asyncio.gather` in declaration order; engine state mutates
  only between gathers.
- The determinism suite asserts byte-identical world logs across runs and
  across processes with different `PYTHONHASHSEED` values.

## Record and replay

Recording runs the day against OpenRouter (default model
`deepseek/deepseek-v4-flash-0731`) and writes every request/response pair
into a cassette directory:

```bash
OPENROUTER_API_KEY=... uv run python -m workbench.simulation.demo \
    --seed 42 --mode record --out out/legal-day \
    --cassette src/workbench/workplaces/legal/cassettes/day-seed42
```

Replay needs no network and is byte-deterministic:

```bash
uv run python -m workbench.simulation.demo \
    --seed 42 --mode replay --out out/legal-day-replay \
    --cassette src/workbench/workplaces/legal/cassettes/day-seed42
```

Committing the cassette activates the full-day acceptance suite in
`workplaces/tests/test_demo_acceptance.py` (byte-identity, validator, volume,
storyline milestones, the unwritten-standard litmus).

**Re-recording:** any prompt-affecting change — persona text, signature
docstrings, dspy version, compiler version — orphans cassette entries, and
replay fails loud with a `CassetteMissError`. Record into a fresh cassette
directory, review the new day, commit both together. Cassettes are keyed by
request content, not call order, so unrelated changes leave entries valid.

## The externalized seat

`ExternalEntity` + `ActTransport` (in-process, scripted, stdio JSONL) let an
external process play any seat; the engine cannot tell the difference, and
the round-trip test proves injected actions resolve identically. This is the
integration point for evaluation harnesses and future online, real-time
operation (swap `EventDrivenTimeModel` for a wall-clock `TimeModel`).

## Deliberate v1 boundaries

- The GM makes no LM calls: repair (`RepairIntent`) and freeform grounding
  (`ResolveFreeform`) are named DSPy targets for the optimization phase.
- No prefab registry: `WorkplaceSpec` is the scenario-as-data seam; a
  registry earns its place when multiple persona types exist.
- No vector memory in the demo path: working-memory folds are exact and
  deterministic. `AssociativeMemory` lands when a workplace outgrows folds.
- Worlds are static-plus-reactive; internal personas act when addressed or
  scripted. Self-initiated wake-ups ride on the existing timer machinery
  when needed.
- GEPA optimization starts once recorded days provide metrics to optimize
  against; `workbench.simulation.registry.programs()` enumerates the
  optimizable programs, and cassette entries carry call-site metadata for
  slicing traces per predictor.
