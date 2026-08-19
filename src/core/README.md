# workbench (core, environment)

The contract side of the system, in two modules of one distribution:

* **`core`** — the typed vocabulary of professional work: events
  (email, chat, documents, tickets, calendar, people), the intents that
  produce them, action specs, deterministic ids and seeds, and the world
  log — an append-only JSONL stream with a validator that proves every
  reference resolves.
* **`environment`** — `materialize(world_log, out_dir)`: validate
  the log, project the databases via [`tools/`](../tools/), and write the
  environment bundle an MCP client inhabits:

  ```
  <out_dir>/               bundle root — never the agent's working directory
    environment.toml       runner config, including the agent workspace path
    mcp.json               server launch specs, db paths bundle-relative
    state/*.db             offstage: only the environment user reads these
    workspace/             becomes /home/agent/workspace
      <document files, laid out as a professional's folders>
  ```

  The split is the offstage boundary made structural: the agent's working
  directory holds documents and nothing else, so the emulated products are
  the only route to the record.

The tool systems themselves (projections, MCP servers, coherence) live in
the [`tools/`](../tools/) member.

Nothing here knows about legal work, simulation, or language models. If a
concept only makes sense for one domain or one layer, it does not belong
here.

The container image the bundles run in (`Dockerfile`,
`run-as-environment.c` setuid shim) lives at the repo root under
`environment/`.

Start with [`docs/WORKBENCH.md`](../../../docs/WORKBENCH.md) for how
these contracts are used.
