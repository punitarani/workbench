# workbench (core, tools, environment)

The agent-facing side of the system, in three modules of one distribution:

* **`workbench.core`** — the typed vocabulary of professional work: events
  (email, chat, documents, tickets, calendar, people), the intents that
  produce them, action specs, deterministic ids and seeds, and the world
  log — an append-only JSONL stream with a validator that proves every
  reference resolves.
* **`workbench.tools`** — projections of the world log into per-tool SQLite
  databases (`mail.db`, `chat.db`, `dms.db`, `matters.db`), read-only MCP
  servers over them, and a cross-database coherence checker.
* **`workbench.environment`** — `materialize(world_log, out_dir)`: validate
  the log, project the databases, and write `.mcp.json` plus
  `environment.toml` so an MCP client can inhabit the workspace.

Nothing here knows about legal work, simulation, or language models. If a
concept only makes sense for one domain or one layer, it does not belong
here.

Also here, under `environment/`: the `Dockerfile` and `run-as-environment.c`
setuid shim — the container image for the Phase 2+ agent environment.

Start with [`docs/simulation-engine.md`](../docs/simulation-engine.md) for
how these contracts are used.
