# Working in adapters

Root rules in [`AGENTS.md`](../../AGENTS.md) apply. Package-specific:

* **The harness sees the environment exactly as an agent does**: the
  bundle's stdio servers, and the documents in `bundle/workspace`. Never
  import `simulation` or `workplaces`, and never read a
  tool database directly from harness code.
* **The episode runs in `bundle/workspace`, never in the bundle root.**
  `run_episode` takes the agent workspace and `write_file` is confined to
  it; only `open_workspace` (server launch) and `grade_episode` (the
  verifier's `WORKBENCH_STATE`) touch the bundle root.
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
