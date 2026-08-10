# Running Hartwell on Harbor with Codex

This is the implemented runbook, not a proposed migration.

## Pinned stack

- Harbor 0.18.0.
- Reward Kit 0.1.7, preinstalled in `workbench:dev`.
- Codex 0.147.0.
- Custom Harbor agent:
  `workbench.adapters.harbor_matrix.codex_agent:HartwellCodex`.
- Agent timeout multiplier: 2.0.
- Codex local compaction through custom provider `hartwell_gateway`.

## Provider routes

The host gateway accepts Responses requests from containers, restores the full
OpenRouter model ID, injects the provider object, and proxies streaming bytes
unchanged.

| Harbor alias | OpenRouter model | Enforced providers |
|---|---|---|
| `gpt-5.6-luna` | `openai/gpt-5.6-luna` | OpenAI |
| `glm-5.2` | `z-ai/glm-5.2` | Baidu FP8, Novita FP8, StreamLake FP8 |
| `deepseek-v4-flash-0731` | `deepseek/deepseek-v4-flash-0731` | Baidu FP8, GMI Cloud FP8, Baseten FP8 |

`allow_fallbacks` is always false. The report records the enforced route and
request sequence span. Actual selected provider remains `null` unless the
upstream Responses API exposes it.

## Secret boundary

Set `OPENROUTER_API_KEY` only in the host environment. For this workspace the
operator used:

```shell
uv run --env-file /Users/punit/projects/workbench/.env \
  python -m workbench.adapters.harbor_matrix \
  --run-id <unique-run-id> \
  --projected-worst-case-batch-usd <full-nine-cell-projection>
```

The runner creates a random gateway token, writes only that token to a mode-0600
temporary env file, passes the path to Harbor, and deletes it after the launch.
The OpenRouter key never enters a container or command line.

## Task environment

Each task references `workbench:dev`. `harbor_stage.py` installs four
argument-free stdio MCP wrappers and an argument-free reference wrapper. State
and runtime live in environment-owned mode-0700 storage and staged source is
removed before the agent starts. The agent cannot read databases, import the
runtime, call arbitrary commands through `run-as-environment`, or observe
offstage truth.

The MCP servers are Gmail, Slack, iManage, and Clio. Their current public tool
counts are 4, 9, 9, and 8.

## Reward contract

Every task runs Reward Kit once over `answer` and `process` criteria.

- `answer`: deterministic content score; F1/exact splits for set fields.
- `process`: surface use and turn efficiency from the Codex trajectory.
- canonical `reward.json`: `reward = answer`, plus separate `answer` and
  `process` fields.
- missing or malformed deliverable: zero.
- reference solution: `reward=answer=1`, `process=0`.

The matrix runner rejects a cell unless the trial has no exception, Codex is
0.147.0, all three metrics are finite and in `[0,1]`, and `reward == answer`.

## Launch protocol

The runner executes in this order:

1. one fee attempt per model;
2. two more fee attempts per model;
3. client departure, three attempts per model;
4. billing hygiene;
5. second read;
6. visitor log;
7. operative deadline;
8. standard drift;
9. vanished clause.

No more than eight agents run concurrently. Existing report or job paths,
including symlinks, are fatal before Harbor starts. This prevents Harbor resume
semantics from relabeling stale trials.

The CLI projection is the worst-case cost of a full nine-cell task batch. A
three-cell smoke uses one third and a six-cell continuation uses two thirds.
After every launch, observed cost is normalized back to full-batch units and
becomes the new floor for later projections. Every launch retains the `$1.50`
reserve and every return is metered before result validation.

## Current resume status

The 2026-08-10 run stopped after the fee matrix at meter
`56.005689513`, leaving less than the reserve. Because source hardening commit
`dd6e11f` followed the paid diagnostics, a future authorized run must start a
new run ID and rerun all eight task matrices from one clean fingerprint. Do not
reuse invalid compaction or timeout trials.
