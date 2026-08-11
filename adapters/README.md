# adapters

Bridges from the Workbench environment to outside consumers — model-eval
harnesses today, non-Harbor frameworks (Prime, Tinker, …) when a concrete
second consumer exists. This is the `workbench-adapters` distribution,
importable as `workbench.adapters`.

The first member is the model-eval harness
(`workbench.adapters.harness`): open a materialized bundle's MCP servers
over stdio from the bundle root (`mcp_workspace`), run a tool-calling
chat model in an episode loop confined to `bundle/workspace` with
`write_file`/`finish` builtins (`agent_loop`), grade the resulting
workspace with the task's own grader (`grade`), and report per-attempt
scores, best-of-N, and token usage (`cli`). The only real model client is
`openrouter_client`; everything else is provider-agnostic behind the
`ChatClient` protocol.

Run one model against one Harbor task (the only place a key is needed):

```bash
OPENROUTER_API_KEY=... uv run python -m workbench.adapters.harness.cli \
    --task datasets/legal-nda/tasks/vantage-triage \
    --model deepseek/deepseek-v4-flash-0731 --attempts 3
```

Tests script the chat client; nothing in this package's test suite calls
a paid model.

RL-framework adapters remain deferred: the engine's `ActTransport`
protocol (`simulation/src/workbench/simulation/external/`) is the seam
one will plug into when a named target framework arrives.

The Hartwell Harbor matrix runs through a local Responses gateway that restores
the full OpenRouter model IDs and enforces the recorded provider order. The real
OpenRouter key stays in the host process; containers receive only an ephemeral
gateway token. Supply a conservative projection for a full nine-cell task batch
so the runner can scale smoke/continuation launches and enforce the recorded
project cap and in-flight reserve:

```bash
OPENROUTER_API_KEY=... uv run python -m workbench.adapters.harbor_matrix \
    --run-id final-matrix \
    --projected-worst-case-batch-usd 3.00
```

An explicitly authorized continuation can start a new spend ledger and select
only the task batches that need fresh cells:

```bash
OPENROUTER_API_KEY=... uv run python -m workbench.adapters.harbor_matrix \
    --run-id hard-task-matrix \
    --task vanished-clause \
    --budget-baseline-usage 56.005689513 \
    --project-cap-usd 12.50 \
    --projected-worst-case-batch-usd 8.00
```

Repeated `--task` flags are normalized to the suite's canonical order. Each
selected task still runs exactly three attempts for each of the three pinned
models; omitting the flag retains the full eight-task protocol. The recorded
budget baseline and incremental cap are written to the matrix report. Credits
are polled every 30 seconds while Harbor is running; the runner terminates the
paid process group if observed in-flight cost exceeds the launch's authorized
projection or reaches the `$1.50` reserve. The interval can be tightened with
`--credit-poll-interval-sec` for unusually expensive routes.

The runner pins Harbor 0.18.0 and Codex 0.147.0, uses a 2x agent-time multiplier,
and includes that execution setting in every fingerprint. It first runs one fee-dispute
smoke trial for each model, validates that the complete task and materialized
environment fingerprint is unchanged, and reuses those trials as attempt one.
It then runs two more fee attempts per model and three attempts per model for
each remaining task, one task batch at a time. Credits are metered before paid
work, during every launch, and after every launch. The incremental report under
`jobs/` records each
attempt's fingerprint, enforced routing order, unobserved actual-provider
status, request-sequence spans, spend, and any failure that stops the run.
