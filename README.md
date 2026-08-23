# Workbench

Workbench is a factory for reinforcement-learning environments of
realistic professional work. It gives an agent a believable workspace —
the files, systems, colleagues, and interruptions of an actual job — so
that evals, benchmarks, and post-training datasets measure competence
rather than puzzle-solving.

Realism comes from a simulation that runs offstage. A clean-room,
LLM-first multi-agent engine (Concordia's pattern, none of its code)
plays every employee and client of a professional firm day by day and
writes one validated world log; every model call is recorded into
content-keyed cassettes so a recorded world replays byte-identically
with no network. The log is materialized into an environment of emulated
products — Gmail, Google Calendar, Slack, iManage Work, and practice
management, each a SQLite-backed MCP server held to pinned vendor-parity
snapshots in CI. The agent never sees the simulation itself: workspace
documents and the product tools are its only windows into the world.

Tasks are built on those environments in
[Harbor](https://www.harborframework.com/docs)'s format and graded
against oracles computed from the same world state, with measured
frontier baselines recorded per task. Current worlds: a litigation firm
(Hartwell, frozen), two 17-person CPA firms (Calder & Finch with a full
six-month epoch; Ashgrove Reid as the assurance-led comparison), and the
original single-day legal demo.

**[`docs/WORKBENCH.md`](docs/WORKBENCH.md) is the single source of
truth** — mission, as-built architecture, worlds and their measured
numbers, the fidelity ledger, every command. Working rules for agents
and contributors are in [`AGENTS.md`](AGENTS.md).

## Quickstart

```bash
uv sync                                   # install the Python workspace
uv run pytest                             # run the test suite
docker build -f environment/Dockerfile -t workbench:dev environment
```

Run a task against the image with Harbor:

```bash
harbor run -p datasets/<dataset>/tasks/<task> -a claude-code -m <model>
harbor view                               # inspect trajectory, verifier logs, reward
```

Tasks reference the prebuilt image through `[environment].docker_image`
in `task.toml`, so a dataset run does not rebuild the environment per
task.

## Repository layout

```
src/  one Python distribution, one import namespace
  core/           typed contracts: events, intents, actions, world log
  simulation/     the LLM-first, deterministic simulation engine
  workplaces/     concrete firms as data (legal, hartwell, calder, ashgrove)
  tools/          agent-facing tool systems: projections and MCP servers
  environment/    workspace materialization and bundle assembly
  artifacts/      renderers for spreadsheets, documents, decks
  analysis/       stdlib statistics and the fidelity harness
  adapters/       eval harnesses: models against finished bundles
tests/          mirrors src/; parity snapshots under tests/parity/
environment/    container image: Dockerfile, setuid shim
datasets/       Harbor tasks and their builders, grouped into datasets
scripts/        show_shape.py       what a db or oracle actually contains
                mutation_check.py   break code on purpose, confirm tests notice
                check_gates.sh      every build refusal, broken (a CI step)
                measure_new_corpus.sh  a finished recording, measured end to end
                fidelity_report.py, rollout.py, export_world_log.py
docs/           WORKBENCH.md plus measurement records
```
