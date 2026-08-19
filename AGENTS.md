# Agent guide

Workbench is a factory for RL environments of realistic professional
work. [`docs/WORKBENCH.md`](docs/WORKBENCH.md) is the single source of
truth for what it is; [`docs/METHOD.md`](docs/METHOD.md) is how to build
worlds, cut tasks, and measure models without fooling yourself; this
file is how to work in the repo.

## Principles

* **Lean.** Every dependency, package, layer, and file must justify itself. Delete before you add.
* **Agent-first.** Code, layout, and docs are read by agents more than by people. Favor explicit names, discoverable structure, typed contracts, and failures that explain themselves.
* **Fast.** This runs thousands of trials. Startup cost, image size, and per-turn latency are correctness concerns.
* **Domain-neutral core.** Finance, legal, consulting, and administrative knowledge lives in `workplaces/` and `datasets/` only.

## Layering

```
core  ←  simulation  ←  workplaces
  ↑
environment / tools          adapters
```

The eight top-level packages live directly under `src/`; there is no
`workbench` package directory. The distribution is still named
`workbench` and installs all eight, so `src/core` imports as `core`.

* Dependencies point inward toward `core`. With no shared import prefix, `tests/test_layering.py` is the only thing enforcing this — a new top-level package must be added to its rules, to `[tool.uv.build-backend] module-name`, and to `tests/core/test_core_namespace.py`, which fails until all three exist. Never import outward or sideways.
* `core` owns the event vocabulary: the typed primitives of professional work (messages, tickets, documents, calendar, intents). Tools own their presentation schemas; simulation owns behavior; workplaces compose both. New payload kinds are declared in core's closed union, never elsewhere.
* `environment` and `tools` must not import `simulation` or `workplaces`.
* `adapters` depends on `core` and task formats — never on a workplace.
* `datasets/` is data plus scripts. It imports nothing from the workspace at task runtime.
* Layering is enforced by `tests/test_layering.py`.

### The offstage boundary

The agent must never observe simulation internals — personas, hidden state, private reasoning, ground truth, or reward logic. Simulation reaches the agent two ways only:

1. **Materialized data**, generated before a run and seeded into the workspace.
2. **Tool servers** over the projected databases, running as the `environment` user; writes land in action tables and grading reads the resulting state.

`ToolSystem` structurally refuses `sim.*` tags. Any new agent-facing surface needs an explicit contract describing what it reveals. When in doubt, reveal less.

### Determinism and cassettes

* Every generator and simulation entry point takes an explicit seed and produces identical output for identical input. No wall-clock reads, no unseeded randomness, no dependence on dictionary or filesystem ordering (ruff bans the offending stdlib calls).
* Every LM call goes through the content-keyed cassette store. **Prompt-affecting changes — signature docstrings, field descriptions, schema fields, the sequence of LM calls — invalidate recorded cassettes**; replay then fails loud with `CassetteMissError`. Re-record deliberately and commit change plus cassette together. Everything downstream of the world log (projections, servers, renderers, graders) is cassette-safe by construction.
* Failures are loud: cassette misses, budget exhaustion, and transport failures always raise. Never degrade silently.

## Python

* Python 3.14. `uv` for dependencies and tools, `uv run` to execute. Never `pip` or `python -m venv` directly.
* Pydantic v2 models at every boundary: config, tool inputs and outputs, simulation state, generated artifacts. No bare dicts crossing a module edge.
* Full annotations. Prefer precise types (`Literal`, `NewType`, discriminated unions, `Protocol`) over `Any` and over defensive `isinstance` checks.
* Async by default for I/O. Keep sync and async paths separate rather than bridging them.
* Errors are typed and specific. Fail at the boundary where the bad input arrived.
* Single distribution: all code lives in `src/<subpackage>/`, tests in `tests/<subpackage>/`.

## Style and comments

* Match the surrounding code. Small, single-purpose functions; names that make a comment unnecessary.
* Comment only what code cannot say: a non-obvious constraint, an invariant, a deliberate trade-off, a reference for a magic value.
* Never narrate the code, restate a signature, mark a section, or explain a change you just made. That belongs in the commit message or PR.
* No emojis. No decorative separators.

## Tests

* `pytest` for everything. Test behavior at contracts, not internals.
* Every simulation generator gets a determinism test: same seed, same bytes.
* Every agent-facing tool gets a test asserting it does not leak offstage state.
* Fixtures over mocks. Mock only what leaves the process. No paid LM calls in tests (`real_lm`-marked tests are opt-in and excluded by default).
* Cassette-gated acceptance suites skip when their recording is absent; committed cassettes (Calder two-day, flagship week) replay in CI.

## Commands

```bash
uv sync                       # install the workspace
uv run pytest                 # tests (quiet, real_lm excluded)
uv run ruff check --fix .     # lint
uv run ruff format .          # format
```

Both ruff commands must pass before work is considered done.

Build the environment image with `environment/` as the build context, since the Dockerfile copies files relative to it:

```bash
docker build -f environment/Dockerfile -t workbench:dev environment
```

Epoch runners, task builders, the fidelity report, and the eval harness are catalogued with their real invocations in [`docs/WORKBENCH.md`](docs/WORKBENCH.md).

## Measuring models

Read [`docs/METHOD.md`](docs/METHOD.md) before building a task or
reading a score. Four rules from it that are violated most often:

* **Only a model failure may ship.** A score below 1.0 is a defect —
  environment, data, harness, or task — until proved otherwise. Task
  defects are the most common and look exactly like model failures.
* **A check that cannot fail is not a check.** Verifying a disputed row
  by re-running the pattern that produced it agrees by construction.
  Falsify every gate once, deliberately, before trusting it.
* **A zero is not a score.** Harness incompatibility, rate limits, the
  clock, and abandoned delegation all produce 0.000. Read the trial log
  before recording the number, and never average a non-answer as a zero.
* **Identical failures across independent trials are a task defect.**
  Genuine model error is stochastic. A defect blocks every trial;
  difficulty just makes most of them miss.

When a measurement teaches something that will hold on the next dataset,
add it to `METHOD.md`. Run records under `docs/runs/` are history and are
not read by the next build.

## Tasks and datasets

A task is `datasets/<dataset>/tasks/<task>/` in Harbor's format: `task.toml`, `instruction.md`, `solution/`, `tests/`.

* Reference the prebuilt image via `[environment].docker_image`; do not add a per-task Dockerfile without a reason.
* The workspace is `/home/agent/workspace`. Rewards go to `/logs/verifier/`.
* Prefer weighted, partial-credit criteria for read tasks; write-workflow tasks grade conjunctive outcomes on action-table state. Every task ships a reference solution that earns full reward, and builders verify it against the committed oracle byte for byte.
* `instruction.md` is a professional's brief, not a task spec. Nothing the agent can reach may name the offstage databases.

## Container

The image is layered stable-to-volatile so sibling environments share the `base` stage cache. Put shared, rarely changing setup in `base`; put heavy or environment-specific packages in the final stage. Pin versions with a top-level `ARG`. Users are fixed: `environment` (10000), `agent` (10001), `verifier` (10002), `sandbox` (10003) — do not renumber them. The image ships Python 3.14, Node, Bun, and pnpm for task use; the repo itself is Python only.

## Do not

* Run servers, long-lived processes, `harbor run`, or a recording epoch unless asked.
* Add a dependency, package, or abstraction layer for a single caller.
* Put documentation anywhere but `docs/`, except `README.md`/`AGENTS.md` files: every top-level package carries both, and a subfolder may carry an `AGENTS.md` when it has invariants worth stating where the code lives. There are exactly two narrative documents and they do not overlap — `docs/WORKBENCH.md` describes what exists, `docs/METHOD.md` describes how to build and measure. Extend one of them rather than adding parallel plans, ADRs, or status files. Links between documents are relative and CI-checked, anchors included — docs are a surface no code imports, so moving or renaming one silently breaks every link into it.
* Widen an agent-facing surface, weaken a type, or loosen a permission to make a test pass.
* Loosen a fidelity band or edit a parity snapshot to turn a failure green; both are deliberate, reviewed commits.
