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
frontier baselines recorded per task.

**The shipping pack is `merrick` and `delegation`** — one 31-person law
firm recorded twice, 180 and 135 days, carrying twelve live tasks of which
eight are certified against three model tiers. **[`docs/PACK.md`](docs/PACK.md)
is what to read first**: what the tasks measure, what they do not, and the
floors and completion rates beside every score.
[`docs/CERTIFIED.md`](docs/CERTIFIED.md) holds every trial score with the
command that reproduces it, and [`docs/TASKS.md`](docs/TASKS.md) is a
generated index of every task.

Four earlier worlds remain in the tree and are **not** part of that pack:
a litigation firm (Hartwell, frozen), two 17-person CPA firms (Calder &
Finch, Ashgrove Reid) and the single-day legal demo. Their tasks predate
the current grading architecture and the scorer refuses them; `ashgrove`
is the world whose tasks measured at ~1.000 for a frontier model however
the difficulty was turned up, which is why `merrick` was recorded.

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
scripts/        certify.py          the publication gate: band, tiers, waivers
                band.py             the three-tier mean, and whether it is real
                completion.py       how often a tier produced the deliverable
                regrade.py          re-score saved answers against a new key
                coherence.py        do the surfaces agree about who is busy
                dead_conditions.py  rule conditions that decide nothing
                adjudicate.py       judge a disputed row against the source
                port_task.py        cut a task from one world into another
                task_index.py       regenerate docs/TASKS.md
                show_shape.py, mutation_check.py, rollout.py, sweep_queue.py
docs/           WORKBENCH.md plus measurement records
```
