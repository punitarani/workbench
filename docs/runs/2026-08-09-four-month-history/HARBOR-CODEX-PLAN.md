# Running the suite on Harbor with the Codex harness

Supersedes the Pi approach in HARBOR-MIGRATION.md §4. Everything below is
read from `harbor/agents/installed/codex.py` in the installed package.

## Why Codex, concretely

| requirement | Codex | Pi |
|---|---|---|
| Registers task MCP servers | **yes** — `_build_register_mcp_servers_command()` writes `[mcp_servers.<name>]` blocks into `$CODEX_HOME/config.toml` | **no** — `run()` never reads `self.mcp_servers` |
| Non-OpenAI models | **yes** — `OPENAI_BASE_URL` is honored *and* written into `config.toml` (source comment: codex 0.118.0 reads it only from config, not the env) | n/a |
| Code execution | **yes** — `codex exec --enable unified_exec` | yes |
| Resume across steps | `SUPPORTS_RESUME` | yes |

Code execution is the decisive one. The failure audit found our
exhaustive-recall tasks (1,427 activities × 8 people × 120 days) were
partly measuring in-context bookkeeping stamina, because our harness gave
the agent no way to compute. Codex can write and run a script — the same
thing a real billing coordinator does with a spreadsheet.

## How Codex is wired (verified)

**Install**: `npm install -g @openai/codex@<version|latest>` as the agent
user, under nvm. Pin with `--ak version=<x.y.z>` for reproducibility.

**MCP registration**, per server declared in `[[environment.mcp_servers]]`:
```toml
# appended to $CODEX_HOME/config.toml  (CODEX_HOME=/tmp/codex-home)
[mcp_servers.gmail]
command = "run-as-environment python3 -m workbench.tools.serve gmail --db /home/environment/state/gmail.db"
```
Note the shape: for `transport = "stdio"` Codex takes **one joined command
string** (`shlex.join([command] + args)`), not a command/args split. For
`sse`/`streamable-http` it writes `url = "..."` instead.

**Auth**: `OPENAI_API_KEY` by default (written to `auth.json` and symlinked
into `$CODEX_HOME`), or a real `auth.json` via `CODEX_AUTH_JSON_PATH` /
`CODEX_FORCE_AUTH_JSON`.

**Run**:
```
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
  --model <model> --json --enable unified_exec -- "<instruction>"
```
Harbor parses `last_token_usage` from the JSON stream for cost accounting.

## Provider strategy for a three-model matrix

OpenRouter is OpenAI-compatible, so all three models run through Codex by
pointing it at OpenRouter:

```bash
harbor run -p datasets/hartwell -a codex \
  --ae OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
  --ae OPENAI_API_KEY=$OPENROUTER_API_KEY \
  -m openai/gpt-5.6-luna -m z-ai/glm-5.2 -m deepseek/deepseek-v4-flash-0731 \
  -k 3 -n 24 --n-concurrent-agents 8 \
  --ve OPENAI_API_KEY=$OPENROUTER_API_KEY \
  --ve OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
  -o jobs/ --job-name codex-matrix-01
```

**Risk to validate first**: Codex is built for OpenAI models and may assume
provider-specific behavior (reasoning params, tool-call formatting, streaming
shape). GLM and DeepSeek through an OpenAI-compatible shim is plausible but
unproven. Validate with one task × one attempt per model *before* the matrix;
if a model misbehaves under Codex, that is a harness artifact and must be
reported as such, never as a task result.

**Provider pinning**: our `MODEL_PROVIDERS` map (openai; baidu/novita/
streamlake fp8; baidu/gmicloud/baseten fp8) has no equivalent here — Codex
sends a bare model string. Either accept OpenRouter's default routing for the
Harbor matrix (and say so), or pass provider preferences through OpenRouter's
`provider` field if Codex forwards unknown body keys (it likely does not).
This is a real reproducibility regression versus our own harness; document it.

## Network posture

Agent phase needs egress to the model provider, so `network_mode` cannot be
`no-network` as I proposed for the stdio design. Use `allowlist`:

```toml
[environment]
network_mode = "allowlist"
allowed_hosts = ["openrouter.ai"]
```

The tool databases stay unreachable by *filesystem* placement, not network
policy — or, better, move them behind the sidecar (below) so the agent has no
path to them at all.

## Sidecar option (strongest isolation, local Docker only)

Rather than stdio-behind-`run-as-environment`, run the four tool servers as a
compose service and give Codex URLs:

```toml
[[environment.mcp_servers]]
name = "gmail"
transport = "streamable-http"
url = "http://tools:8000/gmail/mcp"
```

The agent container then has **no filesystem path to the SQLite files at
all**. Requires: a streamable-http mode on our servers (mcp 2.0 supports it),
`environment/docker-compose.yaml` with a healthcheck, and `--env docker`
(compose is local-Docker only — cloud backends take single-Dockerfile tasks,
so keep the stdio form as the portable fallback).

## Sequence

| step | action | gate |
|---|---|---|
| 1 | start Docker; build `workbench:dev` | image exists |
| 2 | `uv tool install harbor-rewardkit[all]`; port **one** task's grader to the Reward Kit layout with the F1 criterion | rewardkit reproduces the old score on solve.sh output |
| 3 | rewrite that task's `task.toml` to the real schema (PackageInfo, mcp_servers, agent/verifier users) | `harbor check` passes |
| 4 | `harbor run -p <task> -a codex -m openai/gpt-5.6-luna -k 1 -n 1` | non-zero reward; MCP tools visible in the trajectory |
| 5 | repeat step 4 for GLM and DeepSeek | confirms the OpenAI-compat shim works per model |
| 6 | port remaining tasks; add judge + trajectory dimensions | each passes `harbor check` |
| 7 | full matrix, `-n 24` | matrix reproduces or explains deltas vs the adapters harness |

Steps 4–5 are the real risk. Everything after is throughput.

## What changes in the results

Expect scores to **rise** — code execution plus a stronger agent loop removes
the bookkeeping bottleneck the audit identified. That is the point: the
current numbers partly measure our harness's limits, not model competence.
The Codex matrix is the first measurement where a low score can be attributed
to the task rather than the runner, provided steps 4–5 pass cleanly.
