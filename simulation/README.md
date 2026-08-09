# simulation

The engine: a clean-room, typed, async, deterministic rebuild of the
generative agent-based modeling pattern (Concordia's ideas, none of its
code). It simulates a workplace — people with knowledge, style, and
schedules; a game master that grounds their intents into typed world
events; an interrupt-driven loop over simulated time — and records every
model call so a day replays byte-for-byte with no network.

What lives where:

| Package | Purpose |
|---|---|
| `lm/` | LM protocol, OpenRouter backend, cassette record/replay, DSPy bridge |
| `entity/` | Component phase machine, ComposedEntity, DSPy component base |
| `engine/` | InterruptEngine, event queue, attention masks, timers |
| `gm/` | Grounded game master: world state, validation, timeflow |
| `persona/` | Professional personas: params, working memory, DSPy programs |
| `external/` | Externalized seats: transports for agents outside the process |
| `workplace/` | Spec + deterministic compiler from org definition to a runnable day |
| `audit/` | Mechanical realism checks over finished world logs |

Run a day: `python -m workbench.simulation.demo` (see
[`docs/simulation-engine.md`](../docs/simulation-engine.md) for the
record/replay workflow and the architecture in full).
