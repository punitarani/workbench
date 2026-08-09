# Harbor migration + improvement plan

Schemas below are read from the installed `harbor` package
(`harbor.models.task.config.TaskConfig`, `harbor.models.task.paths.TaskPaths`)
and from Reward Kit's source, not from prose docs.

## 0. Blockers, stated first

| blocker | state | fix |
|---|---|---|
| Docker daemon | **down** | start Docker Desktop |
| `workbench:dev` image | **never built** (`docker images` empty) | `docker build -f workbench/environment/Dockerfile -t workbench:dev workbench/environment` |
| `rewardkit` locally | absent (lives in the image) | `uv tool install harbor-rewardkit[all]` for authoring/testing |

Nothing below can be verified end to end until the image exists.

## 1. What is non-conformant today

Our `task.toml` is only partly valid Harbor:

| we write | Harbor's actual schema |
|---|---|
| `[task] name, dataset, summary` | `[task]` is **PackageInfo**: `name*`, `description`, `authors[]`, `keywords[]`. No `dataset`, no `summary` (dataset membership lives in a `dataset.toml`) |
| `[verifier] weights = {...}` | `[verifier]` is `network_mode`, `allowed_hosts`, `timeout_sec`, `env{}`, `user`, `environment_mode`, `environment{}`, `collect[]`. **No `weights`** — weighting belongs to Reward Kit criteria |
| `[harness] max_tool_calls` | **Harbor has no per-task call budget.** Agent limits are `agent.timeout_sec`. Our call-budget policy has no Harbor equivalent |
| `.mcp.json` beside the bundle | `[environment] mcp_servers` is **first-class in task.toml** (`name*`, `transport` = stdio\|sse\|streamable-http, `url`, `command`, `args[]`), plus `harbor run --mcp-config` |

Canonical layout (`TaskPaths`): `task.toml`, `instruction.md`, `README.md`,
`.gitignore`, `environment/`, `solution/solve.sh`, `tests/`.

**Consequence for the call budget.** The 3×-floor policy was load-bearing in
our results (it is what pushed Luna from 1.00 to 0.44 on several tasks) and it
does not survive migration as-is. Options: (a) drop it and rely on
`agent.timeout_sec`; (b) enforce it inside the MCP servers (count calls, refuse
past N — server-side, so it survives any harness); (c) grade *process* with
Reward Kit's `trajectory_turn_count`, which decays linearly past a max rather
than cutting off. **(b) + (c) is the honest replacement** — (b) keeps the
constraint real, (c) makes efficiency a graded dimension instead of a cliff.

## 2. Target task.toml

```toml
schema_version = "1.0"

[task]
name = "fee-dispute-reconstruction"
description = "Reconstruct the billing facts behind the Meridian April invoice dispute"
authors = ["Workbench"]
keywords = ["legal", "billing", "cross-system-retrieval"]

[metadata]
difficulty = "hard"
skills = ["retrieval", "reconciliation", "arithmetic"]

[environment]
docker_image = "workbench:dev"
os = "linux"
workdir = "/home/agent/workspace"
network_mode = "no-network"          # tools are local stdio; nothing needs egress
memory_mb = 2048

[[environment.mcp_servers]]
name = "gmail"
transport = "stdio"
command = "run-as-environment"
args = ["python3", "-m", "workbench.tools.serve", "gmail",
        "--db", "/home/environment/state/gmail.db"]
# ... slack, imanage, clio identically

[agent]
timeout_sec = 1800
user = "agent"

[verifier]
timeout_sec = 900
user = "verifier"
environment_mode = "shared"          # verifier reads /home/environment/state
collect = ["/logs/verifier"]
```

`network_mode = "no-network"` for the agent phase is a real hardening win: it
makes tool-only access enforceable rather than conventional. The judge needs
egress, so the **verifier** phase gets `allowed_hosts` for the model provider.

## 3. Verifier redesign — Reward Kit

Reward Kit discovers a **directory layout**, not one config file. Each subdir of
`tests/` is a scored dimension; `*.py` files register programmatic criteria via
`@criterion`; `*.toml` files with `[judge]` + `[[criterion]]` are LLM-judge
configs; an optional root `reward.toml` aggregates dimensions.

```
tests/
  criteria.py                 # @criterion(shared=True) helpers: set_f1, numeric_close
  retrieval/                  # the hard cross-system work
    entries.py                # set_f1(...) -> float  ← replaces exact-set-or-zero
  accuracy/
    figures.py                # numeric_close(total_minutes, 890, tol=0)
  reasoning/
    judge.toml                # LLM judge over the written justification
  process/
    efficiency.py             # trajectory_tool_used / trajectory_turn_count
  reward.toml                 # cross-dimension aggregation + weights
```

**The single highest-value change**: Reward Kit ships **no** set/F1 criterion and
**no** numeric-tolerance criterion — but custom criteria are first-class, and a
criterion may return a float. So the binary cliff is fixed by ~15 lines:

```python
@criterion(description="Unsupported entries: F1 against the certified set", shared=True)
def set_f1(workspace: Path, path: str, key: str, expected: list) -> float:
    got = set(map(str, json.loads((workspace / path).read_text()).get(key, [])))
    want = set(map(str, expected))
    if not got or not want: return float(got == want)
    tp = len(got & want)
    p, r = tp / len(got), tp / len(want)
    return 0.0 if not tp else 2 * p * r / (p + r)
```

This restores ranking power *and* RL gradient: 6-of-7 correct now scores ~0.92
instead of 0. Keep a separate small-weight `all_pass` criterion if "certified
complete" deserves its own bonus — that preserves the certification semantics
without collapsing the whole score.

**LLM judge** (fixes `vantage-triage`'s 0.92-for-boilerplate):

```toml
[judge]
judge = "openai/gpt-5.6-luna"
files = ["/app/triage.json"]
reference = "/tests/reference/triage.json"
mode = "individual"
weight = 1.0

[[criterion]]
id = "basis.term"
description = """Does the stated basis for the term clause cite the firm's own
two-year vendor standard, as opposed to generic contract language? Answer no if
the text is plausible boilerplate that names no specific source."""
type = "likert"
points = 5
```

Judge caveats found in source, and how to handle them:
- **No temperature control and no multi-sample voting.** Mitigate by keeping
  judge weight modest (≤25%), using `likert` (graduated, less bimodal than
  binary), pinning a specific judge model, and treating judge dimensions as
  *supplementary* to deterministic ones — never load-bearing alone.
- `reasoning_effort` is the only determinism-adjacent knob.
- Judge credentials flow via `--je/--judge-env` or `--ve` on `harbor run`.

**Process criteria** — new capability we never had:
`trajectory_tool_used("slack__slack_read_channel", min_count=1)` directly
encodes "did it actually open a DM," and `trajectory_turn_count(max_turns=N)`
grades efficiency with linear decay. This lets us reward *method*, not just
answer — and would have caught the billing-hygiene episode where a model never
opened a single DM yet still submitted an answer.

**Reward file contract** (verified): Harbor reads
`/logs/verifier/reward.json` as an **arbitrary flat dict of named numeric
metrics** — no mandated `score` key. So Reward Kit's per-dimension output
(`{"retrieval": 0.92, "accuracy": 1.0, "reasoning": 0.7, "process": 0.5}`)
lands natively, and Harbor reports each dimension separately. Exit code is not
inspected; an empty or malformed reward file is a hard error and is *not*
retried.

**Reward Kit concurrency**: `--mcprog 8 --mcllm 8 --mca 2` (programmatic, LLM,
agent-judge). `tests/test.sh` becomes:
```sh
exec uvx --from harbor-rewardkit[all]==0.1 rewardkit /tests --workspace /app
```

## 4. Harness migration — Pi does NOT wire MCP servers

**Blocking finding, verified in Harbor's source.** `pi` is a built-in agent
(`AgentName.PI`, `harbor/agents/installed/pi.py` — it wraps Mario Zechner's
`@earendil-works/pi-coding-agent`), but its `run()` **never references
`self.mcp_servers`**. Claude Code writes task-declared servers into a
user-scoped `.claude.json`; Aider writes `~/.aider.mcp.json`; **Pi does
neither**. An MCP-only environment handed to `-a pi` gives the agent *no
tools at all*.

Options, in order of cost:
1. **`-a claude-code`** — verified to wire `[[environment.mcp_servers]]`
   (stdio → `{"type":"stdio","command","args"}`; http/sse → `{"type":"http"}`),
   deliberately user-scoped to avoid the trust dialog. Use this to get the
   migration working.
2. **Subclass Pi** — `BaseInstalledAgent`, add MCP registration in
   `install()`/`setup()` using Pi's own config mechanism, register via
   `-a workbench.adapters.pi_mcp:PiWithMCP`. This is the path if Pi
   specifically is required.
3. Upstream a patch to Harbor's `Pi` class.

Recommendation: **prove the migration on `claude-code`, then add the Pi
subclass** — otherwise a Pi-shaped bug is indistinguishable from a task bug.

## 4b. The sidecar architecture — better isolation than our bundle split

Harbor gives us something stronger than file permissions, verified in source:

- `tests/` is **uploaded only at verification time** — the agent never sees the
  grader during its run. `solution/` is uploaded **only for the oracle agent**.
  Both of our hand-rolled protections are Harbor-native.
- `[verifier] environment_mode = "separate"` runs grading in a *different
  container* built from `tests/` — the documented pattern for "proprietary
  grading code the agent must not see."
- **Sidecar services**: an MCP server can run as its own compose service with a
  healthcheck, reached over the Docker network
  (`url = "http://tools:8000/mcp"`, transport `streamable-http`). The agent
  container then has **no filesystem path to the SQLite databases at all** —
  not merely unreadable, absent. `[[verifier.collect]]` snapshots sidecar state
  before teardown, and Harbor stops the agent container *before* sidecar
  collection, so it is explicitly un-tamperable.

This supersedes the bundle/state split: instead of trusting directory layout,
the offstage boundary becomes a network boundary. Cost: our stdio servers need
a streamable-http mode (mcp 2.0 supports it) and a compose file, and compose is
**local-Docker only** — cloud backends take single-Dockerfile tasks, so keep
stdio-behind-`run-as-environment` as the portable fallback.

## 4c. What we lose and must consciously replace

| our harness | Harbor/Pi |
|---|---|
| hand-rolled tool loop | Pi's own loop |
| `write_file`/`finish` builtins | Pi's native file tools (**and shell/code execution** — the audit's #1 structural finding) |
| `max_tool_calls` | server-side counter + `trajectory_turn_count` |
| `--attempts 3` best-of-N | `-k/--n-attempts` |
| three shell loops | one job, `-m` repeated |
| custom transcripts | ATIF trajectories, `harbor analyze`, `harbor view` |

**Keep `adapters/` as a fast offline lane** for cheap iteration; Harbor becomes
the authoritative path. Delete nothing until parity is demonstrated on one task.

## 5. Run procedure

```bash
docker build -f workbench/environment/Dockerfile -t workbench:dev workbench/environment

harbor run -p datasets/hartwell -i '*' \
  -a claude-code \
  -m openai/gpt-5.6-luna -m z-ai/glm-5.2 -m deepseek/deepseek-v4-flash-0731 \
  -k 3 -n 24 --n-concurrent-agents 8 \
  --env-file .env \
  --ve OPENAI_BASE_URL=https://openrouter.ai/api/v1 \
  -o jobs/ --job-name matrix-harbor-01
harbor view          # trajectories, verifier logs, rewards
harbor analyze       # trajectory analysis
```

`-a pi` only after the MCP subclass exists (§4). `-n` is the concurrency
lever (default 4); `-k` gives attempts, and a job is the cartesian product
tasks x agents x attempts. With the image
prebuilt and no per-trial build, 16–32 is reasonable on this host; cap agents
separately if the provider rate-limits. One job covers 8 tasks × 3 models × 3
attempts = 72 trials.

## 6. Every improvement, mapped to its mechanism

### Verifier (highest value — the dominant artifact)
1. **Replace exact-set-or-zero with F1** custom criterion. Fixes the 0.44 cliff.
2. **Split "certified complete" into its own small-weight `all_pass`** so the
   semantics survive without dominating.
3. **Add the exact-length guard** (already in `operative-deadline`) wherever a
   set field remains binary — closes the shotgun band where 0.44 = "marked
   everything."
4. **LLM judge for semantic fields** (`vantage-triage.basis`) — kills the
   0.92-for-keyword-stuffing exploit that substring matching cannot.
5. **Numeric tolerance** custom criterion instead of exact equality.
6. **Trajectory criteria** to grade method (opened DMs, tool diversity, turns).
7. **Multi-dimension rewards** (`retrieval` / `accuracy` / `reasoning` /
   `process`) instead of one scalar — Harbor reports them separately, which is
   what makes model ranking informative.
8. State each grader's operative rule verbatim in the instruction (the
   `"Cascadia" in subject` mismatch).

### Environment / data
9. **Fix the Slack DM search gap** — implement `slack_search_public_and_private`
   (the real Slack MCP has it; our omission is what made DMs artificially hard).
10. **iManage search must report which version matched** — currently it silently
    matches superseded text and misleads agents on version-drift tasks.
11. **Clio `ATTORNEY_TITLE_WORDS`** — add "associate"; expose `matter.detail`.
12. **Seat scoping**: honor `WORKBENCH_SEAT` in Slack and iManage; set a seat per
    task so agents aren't omniscient. Pair with `network_mode = "no-network"`.
13. **Project calendar events** into a fifth tool (49 events currently orphaned)
    or drop them from the record.
14. **Add money to Clio** — rate/amount/invoice fields. Without them no
    realistic billing task is expressible.
15. **De-duplicate the corpus**: 91.5% of mail and 86% of chat are templates;
    DMs collapse to 62 strings. Vary generators, or the "filler" keeps creating
    false ambiguity (it caused the Cascadia mismatch).
16. **Weekend/holiday/out-of-hours activity**, realistic billable hours, and
    documents on more than 3 of 10 matters.
17. **Office formats** (docx/xlsx/pdf) — the pipeline is markdown-only; Reward
    Kit's `documents` extra can then grade real files, and tracked-changes
    redlines become expressible.

### Tasks / suite design
18. **Give the agent code execution** (Pi provides it) and re-measure — the
    exhaustive-recall tasks may currently be testing in-context bookkeeping
    stamina rather than competence.
19. **Re-derive call budgets from blind search**, not the oracle script.
20. **Diversify shapes** — 6 of 10 tasks share one anti-join idiom; add
    drafting, judgment, and multi-step tasks with different reward structures.
21. **Generate more than one world** — all bundles are byte-identical today, so
    there is no generalization evidence.
22. **Stop mirroring head-version documents** into the agent workspace where a
    graded field depends on version history.
23. **Run `harbor check`** (built-in task-quality rubric with an evaluator agent)
    on every task — a second opinion we have never used.

## 7. Sequence

| phase | work | gate |
|---|---|---|
| A | start Docker, build image, `uv tool install harbor-rewardkit[all]` | image runs, `rewardkit --help` |
| B | migrate **one** task (fee-dispute) to real `task.toml` + `tests/` layout; F1 criterion; keep the old grader beside it | rewardkit locally reproduces the old score on solve.sh output |
| C | `harbor run` that one task, `-a pi`, one model, `-k 1` | non-zero reward, trajectory visible in `harbor view` |
| D | port remaining tasks; add judge + trajectory dimensions | `harbor check` passes on each |
| E | full matrix as one job, `-n 24` | matrix reproduces or explains deltas vs the adapters harness |
| F | environment/data fixes (9–17), regenerate, re-measure | coherence clean, dedup measured |

Phases A–C are the risk; D–F are throughput. Do not delete `adapters/` until E.
