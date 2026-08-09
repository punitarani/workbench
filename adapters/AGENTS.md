# Working in adapters

Root rules in [`../AGENTS.md`](../AGENTS.md) apply. Package-specific:

* **The harness sees a workspace exactly as an agent does**: `.mcp.json`,
  the stdio servers behind it, and the files on disk. Never import
  `workbench.simulation` or `workbench.workplaces`, and never read a tool
  database directly from harness code.
* **No paid LM calls in tests.** The `ChatClient` protocol in
  `agent_loop` exists so tests script the model; only `cli.py` constructs
  the OpenRouter client, and `OPENROUTER_API_KEY` is required only there,
  at runtime.
* **Graders are the task's own.** `grade.grade_episode` runs the task's
  `tests/grade.py` unchanged in the episode workspace; the harness never
  reimplements reward logic.
* **RL-framework adapters stay deferred** until there is a named target
  framework and a real integration to test against. The environment-side
  seam is `ActTransport`; build against it rather than reaching into the
  engine.
