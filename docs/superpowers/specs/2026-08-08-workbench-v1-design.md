# Workbench v1 design

Date: 2026-08-08. Status: draft for review.

Workbench is a reinforcement-learning environment for realistic professional work. This document fixes the v1 architecture: a Concordia-based generative simulation at the center, an MCP tool surface the agent inhabits, and a task factory that turns simulated history into Harbor tasks. It supersedes nothing; it is the first spec.

## 1. Center of gravity

The multi-agent simulation engine is the architecturally critical subsystem. It is not a fixture generator in service of hand-authored tasks; it is the factory that produces the world, the tasks, the ground truth, and the colleagues — agentically and synthetically — for professional domains that are realistic but hard.

The pipeline, end to end:

```
workplace definition
        │  parameterizes
        ▼
simulation (Concordia v2)  ──►  world log (typed events)
        │                            │
        │ checkpoint                 ├──► fixtures        (projection into per-tool SQLite + documents)
        │                            ├──► task moments    (mined instants where work exists to be done)
        │                            ├──► ground truth    (extracted from offstage state, to verifier only)
        │                            └──► persona scripts (recorded dialogue for replay backends)
        ▼
runtime: agent occupies one seat  ──►  MCP tools  ──►  Reward Kit score
        │                                                    │
        └──── eval results / RL signal ◄─────────────────────┘
                       │
                       └──► GEPA improves the generator programs
```

One simulation, two modes. During generation the agent's seat is played by a demonstrator model (which also yields the reference solution). During evaluation the same seat is externalized to the real agent under test. Everything else — personas, systems, history — is identical between modes.

## 2. Foundation: Concordia v2

`simulation/` builds on [gdm-concordia](https://github.com/google-deepmind/concordia) (Apache-2.0, PyPI `gdm-concordia >= 2.4`), DeepMind's library for generative agent-based modeling. What we take from it:

* **Entity–component architecture.** Actors are entities assembled from components; game masters are themselves entities. Prefabs + `InstanceConfig` compose a simulation declaratively.
* **Engine loop.** `next_acting → act → resolve`: the engine solicits actions, the game master resolves them into events. Sequential and simultaneous engines exist.
* **Checkpointing.** `checkpoint_callback` fires per step; entities and game masters can be saved and restored mid-episode.
* **Persona backends, already built.** `ScriptedActComponent` plays a fixed script (our replay backend). `PuppetActComponent` gives fixed responses with LLM fallback (our hybrid). A plain LLM-driven entity is our live backend.
* **LanguageModel wrapper pattern.** `seed` parameters on sampling, plus stackable wrappers (`RetryLanguageModel`, `CallLimitLanguageModel`, `NoLanguageModel`).

What Concordia does not have, and what we therefore build:

| Gap | What we build |
|---|---|
| No external actor: the engine calls `entity.act()` internally | **Externalized entity** — an entity whose `act()` is served by an external process. The single most important piece of Workbench's engine layer. |
| Free-text event resolution | **Grounded game master** — resolves actions into typed system events (mail sent, ticket updated, document revised), not narration. |
| No canonical event stream | **World log** — append-only, typed, the single source from which fixtures, tasks, ground truth, and scripts are all projected. |
| No LM call cache | **Record/replay LanguageModel wrapper** — records calls during generation, replays hermetically at runtime, fails hard on cache miss. This is the mechanism behind "same seed, same bytes." |
| Generic social personas | **Professional persona components** — role knowledge, institutional memory, channel-appropriate register, what this person knows that is written down nowhere. |
| Hand-tuned prompts | **DSPy programs, GEPA-optimized** — persona fidelity, GM resolution, and task authoring are DSPy modules optimized against measured quality (GEPA needs ~10²–10³ evals, which fits simulation-priced rollouts). |

## 3. Layering and the event vocabulary

```
workbench.core  ←  workbench.simulation  ←  workbench.workplaces
      ↑                                            │
workbench.environment / workbench.tools  ◄────────┘  (composition, downward)
```

`workbench.core` owns the **event vocabulary**: Pydantic models for the domain-neutral primitives of professional work — `Message`, `Thread`, `DocumentRevision`, `TicketChange`, `CalendarEvent`, `Person`, `Seed`. This is the resolution of the sideways-import problem:

* `workbench.simulation` emits core events (imports core only).
* Each tool in `workbench.tools` knows how to project core events into its own SQLite schema (imports core only).
* `workbench.workplaces.<name>` composes both: it configures the simulation and invokes tool projections to materialize fixtures (imports downward, which the layering allows).

Core owns the vocabulary of professional work, tools own their presentation and state schemas, simulation owns behavior. A new vertical is a new workplace, not a core change.

## 4. The environment (onstage)

Each system the agent can touch is a Python MCP server over stdio, one per system, each owning one SQLite file:

```
/home/environment/state/mail.db      email
/home/environment/state/chat.db      chat (channels + DMs)
/home/environment/state/dms.db       document repository
/home/environment/state/matters.db   matter / request tracker
```

* Databases are `environment:environment`, mode `0600`. Servers launch as `run-as-environment python3 -m workbench.tools.<name>`; the setuid shim drops them to the `environment` user, so the agent cannot open the files at all. The MCP surface is the only aperture.
* A `.mcp.json` written into the workspace at setup points the agent's client at the servers. No ports, no long-lived processes, no readiness gate.
* Each tool ships exactly three things: an MCP surface, a SQLite schema, and a `project()` loader from core events. Nothing else crosses the edge.
* Per-tool databases keep tools independently testable and droppable; cross-tool coherence is inherited from the world log rather than enforced by schema, and a projection-coherence test verifies it.

### Personas at runtime

Comms servers are ordinary tool servers; a persona is whoever is on the other end of a thread. The response backend is declared per environment in the fixture's `environment.toml`, never assumed:

```toml
[tools]
compose = ["mail", "chat", "dms", "matters"]

[personas]
backend = "replay"        # replay | hybrid | live
```

* `replay`: responses come from recorded persona scripts (Concordia `ScriptedActComponent` output). No LLM, no network, fully deterministic. The determinism test suite applies.
* `hybrid`: scripted where recorded, LLM on miss (`PuppetActComponent` semantics), calls recorded back into the cache.
* `live`: a resumed Concordia entity answers from the simulation checkpoint. Exempt from same-seed-same-bytes by declaration.

The offstage boundary holds in all three: persona internals, hidden state, ground truth, and reward logic never cross the MCP surface. Every tool response is audited by leakage tests.

## 5. The task factory

A task is not authored; it is mined and validated.

1. **Simulate.** Run the workplace for a simulated period under the record/replay LM wrapper. Output: world log + checkpoint.
2. **Pick a moment.** A task moment is an instant where work exists: an NDA arrived, a close is due, a partner changed the ask. Task-mining programs (DSPy) propose moments; early on, humans pick them.
3. **Extract ground truth.** From offstage state — entity knowledge, world-log facts — into the verifier bundle. Ground truth lives in `tests/`, never in the workspace.
4. **Author the task.** Instruction, Reward Kit criteria (deterministic core + judge rubric), and `solution/solve.sh` — the demonstrator's recorded solution path.
5. **Validate.** Every candidate task passes a gauntlet before joining a dataset:
   * solvable — `solve.sh` earns full reward;
   * discriminating — a naive baseline earns strictly less;
   * deterministic — replay backends re-materialize byte-identically;
   * leak-free — no tool response reveals offstage state.

GEPA closes the loop: task-quality metrics (discrimination margin, realism judgments, solve-rate spread across models) are the feedback signal for evolving the mining and authoring programs.

### Verification pattern

Layered: deterministic checks on computed artifacts carry most of the weight; a judge rubric (in TOML) scores judgment-laden parts. Where the task should reward consulting a colleague, make an answer *unobtainable* except by asking — a process question converted into an outcome question, so the verifier never reads the offstage transcript.

## 6. First slice: legal NDA triage

Proof that the pipeline works end to end, kept deliberately small.

* **Workplace**: a legal department of five to seven people (GC, counsel with the unwritten standard, paralegal, requesting business unit, outside party), defined in `workbench.workplaces.legal`.
* **Simulation**: a short simulated period producing enough history to make the org feel inhabited — threads, matters, precedent documents in the DMS, a playbook.
* **Task**: an inbound NDA arrives by email. Triage each clause against the playbook; produce a redlined `.docx` and structured `triage.json`; reply. The playbook has a deliberate gap — one clause type whose standard lives only with counsel, reachable via chat. Personas: `replay` backend.
* **Done means**: `uv sync && uv run pytest` passes; `harbor run` produces a scored trajectory; `solve.sh` earns full reward; the naive baseline measurably fails the gap clause; determinism, coherence, and leakage tests pass.

Where generator programs are not yet built, hand-assist is acceptable in the slice — but through the same interfaces the programs will later fill.

## 7. Testing

* **Determinism** — simulate and materialize twice from one seed under replay; assert identical bytes across all databases, documents, and scripts. Applies to `replay` tasks; `hybrid` is deterministic only with a warm cache and is tested in that state; `live` exempt by declaration.
* **Leakage, per tool** — enumerate every MCP tool; assert no response carries persona internals, hidden state, ground truth, or reward logic. Hard check: opening any `state.db` as uid 10001 fails.
* **Projection coherence** — every cross-system reference in any projected database resolves.
* **Discrimination** — `solve.sh` full reward; scripted naive baseline strictly less.
* **Engine** — externalized entity round-trip: an injected action resolves identically to the same action produced internally.

## 8. Container findings

Two permissions in the current image conflict with the offstage rule and need tightening or a documented Harbor-compatibility reason:

* `/logs/verifier` is group-`agent` writable (775) — the agent can read and tamper with reward output.
* `/oracle` is 777 — agent-readable, which matters the moment reference material lands there.

Also open: whether Concordia ships in the final image stage (needed only for `live` personas; `replay` needs nothing) and whether the associative-memory embedder is pinned to a small local model or its outputs cached like LM calls.

## 9. Phasing

* **Phase 0 — foundations.** uv workspace (`workbench`, `workbench-simulation`, `workbench-workplaces`), PEP 420 namespace, core event vocabulary, ruff/pytest, CI. Makes the README's quickstart true.
* **Phase 1 — engine.** Concordia integration: grounded GM, world log, record/replay LM wrapper, externalized entity, professional persona components. A five-person legal-org simulation producing a typed world log, deterministically.
* **Phase 2 — environment.** Tool-server framework; `mail`, `chat`, `dms`, `matters` with projections, leakage and coherence tests; `.mcp.json` wiring; fixtures committed to git.
* **Phase 3 — first task.** NDA triage mined from the history; layered verification; `solve.sh`; discrimination test; full `harbor run` loop.
* **Phase 4 — the factory.** Task mining/authoring as DSPy programs; GEPA optimization against the validation gauntlet; dataset growth; `hybrid` and `live` backends; second workplace (accounting month-end close); adapters when a concrete non-MCP consumer exists.

## 10. Deferred, deliberately

* **`adapters/`** — no package until a real second consumer. An empty distribution is a claim the code doesn't back.
* **Mid-episode world dynamics** (mail arriving unprompted) — the checkpoint + externalized-entity design supports it later; v1 worlds are static-plus-reactive.
* **GEPA before measurement** — optimization starts when there are metrics to optimize against (post-Phase 3), not before.
* **Non-legal domains** — accounting is next, after the factory exists; the engine and tools stay domain-neutral throughout.

## 11. Documentation debts this spec creates

`README.md` and `AGENTS.md` must be updated in Phase 0: simulation described as Concordia-based with the world-log architecture, the adapters row removed until real, DSPy/GEPA scoped to generator programs, and the layering section extended with the event-vocabulary rule (core owns professional-work primitives; tools own their schemas; workplaces compose).
