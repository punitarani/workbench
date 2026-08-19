# simulation

The engine: a clean-room, typed, async, deterministic rebuild of the
generative agent-based modeling pattern (Concordia's ideas, none of its
code), LLM-first. It simulates a firm — generative agents with memory
streams, plans, reflections, and timesheets; LLM client actors stirred
by a seeded season director; a game master that grounds every intent
into typed world events — and records every model call so an epoch
replays byte-for-byte with no network.

What lives where:

| Package | Purpose |
|---|---|
| `lm/` | LM protocol, OpenRouter backend, cassette record/replay, retry/budget/permits, DSPy bridge |
| `entity/` | Component phase machine, ComposedEntity, DSPy component base |
| `engine/` | InterruptEngine, event queue, canonical-prefix batch admission, attention masks, timers |
| `gm/` | Grounded game master: world state, validation, turn grants, timeflow — zero LM calls |
| `persona/` | Professional personas: params, working memory, memory streams, retrieval, DSPy programs, timesheet turn |
| `actors/` | Client actors: the outside world as slim LLM entities |
| `director/` | Seeded quasi-Poisson cue schedules shaped by a workplace's season |
| `external/` | Externalized seats: transports, the interactive SeatSession, the agent-facing MCP seat server |
| `workplace/` | Spec + deterministic compiler (`COMPILER_VERSION`) from org definition to a runnable epoch |
| `chronicle/` | Procedural history builder (genesis, background traffic, templated arcs) |
| `audit/` | Mechanical realism gates over finished world logs |
| `optimize/` | GEPA optimization loop over the registered persona programs |

Top-level modules: `run.py` (durable runs — `run.db`, one transaction
per step, roll-forward resume, `world.jsonl` export), `snapshot.py`,
`telemetry.py`, `time_model.py`, `transcript.py`, `calendar.py`,
`registry.py` (the optimizable programs), `errors.py` (the typed,
always-raised failures).

Run the single-day legal demo with `python -m simulation.demo`
(`--mode record|replay --cassette <dir>`); full epochs run through
`datasets/<world>/run_epoch.py`. Architecture, determinism model, and
the record/replay workflow are in
[`docs/WORKBENCH.md`](../../../docs/WORKBENCH.md).
