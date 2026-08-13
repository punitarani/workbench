# Agent guide

Workbench is a reinforcement-learning environment for realistic professional work. Read [`README.md`](README.md) for what it is; this file is how to work in it.

## Principles

* **Lean.** Every dependency, package, layer, and file must justify itself. Delete before you add.
* **Agent-first.** Code, layout, and docs are read by agents more than by people. Favor explicit names, discoverable structure, typed contracts, and failures that explain themselves.
* **Fast.** This runs thousands of trials. Startup cost, image size, and per-turn latency are correctness concerns.
* **Domain-neutral core.** Finance, legal, consulting, and administrative knowledge lives in `workplaces/` and `datasets/` only.

## Layering

```
workbench.core  ←  workbench.simulation  ←  workbench.workplaces
      ↑
workbench.environment / workbench.tools        workbench.adapters
```

* Dependencies point inward toward `workbench.core`. Never import outward or sideways.
* `workbench.core` owns the event vocabulary: the typed primitives of professional work (messages, tickets, documents, calendar, intents). Tools own their presentation schemas; simulation owns behavior; workplaces compose both. New payload kinds are declared in core's closed union, never elsewhere.
* `workbench.environment` and `workbench.tools` must not import `workbench.simulation` or `workbench.workplaces`.
* `workbench.adapters` depends on `workbench.core` and task formats — never on a workplace.
* `datasets/` is data plus shell scripts. It imports nothing from the workspace at task runtime.

### The offstage boundary

The agent must never observe simulation internals — personas, hidden state, private reasoning, ground truth, or reward logic. Simulation reaches the agent two ways only:

1. **Materialized data**, generated before a run and seeded into the workspace.
2. **Multi-agent modules**, served at runtime behind a tool contract, running as the `environment` user.

Any new agent-facing surface needs an explicit contract describing what it reveals. When in doubt, reveal less.

### Determinism

Every generator and simulation entry point takes an explicit seed and produces identical output for identical input. No wall-clock reads, no unseeded randomness, no dependence on dictionary or filesystem ordering.

## Python

* Python 3.14. `uv` for dependencies and tools, `uv run` to execute. Never `pip` or `python -m venv` directly.
* Pydantic v2 models at every boundary: config, tool inputs and outputs, simulation state, generated artifacts. No bare dicts crossing a module edge.
* Full annotations. Prefer precise types (`Literal`, `NewType`, discriminated unions, `Protocol`) over `Any` and over defensive `isinstance` checks.
* Async by default for I/O. Keep sync and async paths separate rather than bridging them.
* Errors are typed and specific. Fail at the boundary where the bad input arrived.
* Single distribution: all code lives in `src/workbench/<subpackage>/`, tests in `tests/<subpackage>/`. Layering is enforced by `tests/test_layering.py`, not by packaging.

## TypeScript

Use it only where Python is the wrong tool. Bun is the default runtime and test runner; add pnpm only when a package requires it. Zod at every runtime boundary, types inferred from schemas rather than declared twice. `strict` plus `noUncheckedIndexedAccess`; no `any`, no non-null assertions, no `@ts-ignore`.

## Style and comments

* Match the surrounding code. Small, single-purpose functions; names that make a comment unnecessary.
* Comment only what code cannot say: a non-obvious constraint, an invariant, a deliberate trade-off, a reference for a magic value.
* Never narrate the code, restate a signature, mark a section, or explain a change you just made. That belongs in the commit message or PR.
* No emojis. No decorative separators.

## Tests

* `pytest` for Python; `bun test` for TypeScript. Test behavior at contracts, not internals.
* Every simulation generator gets a determinism test: same seed, same bytes.
* Every agent-facing tool gets a test asserting it does not leak offstage state.
* Fixtures over mocks. Mock only what leaves the process.

## Commands

```bash
uv sync                       # install the workspace
uv run pytest                 # Python tests
uv run ruff check --fix .     # Python lint
uv run ruff format .          # Python format
bun test                      # TypeScript tests
bun run typecheck             # tsc --noEmit
bunx oxlint                   # TypeScript / JavaScript lint
```

`ruff` lints Python and `oxlint` lints TypeScript and JavaScript; oxlint has no Python support. Both must pass before work is considered done.

Build the environment image with `environment/` as the build context, since the Dockerfile copies files relative to it:

```bash
docker build -f environment/Dockerfile -t workbench:dev environment
```

## Tasks and datasets

A task is `datasets/<dataset>/tasks/<task>/` in Harbor's format: `task.toml`, `instruction.md`, `solution/solve.sh`, `tests/test.sh`.

* Reference the prebuilt image via `[environment].docker_image`; do not add a per-task Dockerfile without a reason.
* Verify with Reward Kit, preinstalled in the image, so `tests/test.sh` can be `rewardkit /tests`.
* The workspace is `/home/agent/workspace`, exposed as `/app` for Reward Kit's default. Rewards go to `/logs/verifier/`.
* Prefer weighted, partial-credit criteria over binary pass/fail. Judge rubrics belong in TOML, not in Python.
* Every task ships a `solution/solve.sh` that actually earns full reward.

## Container

The image is layered stable-to-volatile so sibling environments share the `base` stage cache. Put shared, rarely changing setup in `base`; put heavy or environment-specific packages in the final stage. Pin versions with a top-level `ARG`. Users are fixed: `environment` (10000), `agent` (10001), `verifier` (10002), `sandbox` (10003) — do not renumber them.

## Do not

* Run servers, long-lived processes, or `harbor run` unless asked.
* Add a dependency, package, or abstraction layer for a single caller.
* Put documentation anywhere but `docs/`, except `README.md`/`AGENTS.md` files: every top-level package carries both, and a subfolder may carry an `AGENTS.md` when it has invariants worth stating where the code lives.
* Widen an agent-facing surface, weaken a type, or loosen a permission to make a test pass.
