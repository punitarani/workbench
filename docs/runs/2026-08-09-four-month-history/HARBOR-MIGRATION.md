# Hartwell Harbor migration record

## Final architecture

All eight Hartwell tasks now use Harbor schema 1.3. They reference the shared
`workbench:dev` image and do not carry task-specific Dockerfiles or a compose
sidecar.

```text
host matrix runner
  -> lifecycle-managed Responses gateway
  -> Harbor Codex 0.147.0 container
  -> four argument-free stdio MCP wrappers
  -> environment-owned staged databases/runtime
  -> Reward Kit 0.1.7 verifier
  -> reward.json: reward=answer, answer, process
```

The portable stdio design replaced the unimplemented sidecar proposal. The
environment image is built from `workbench/environment/`:

```shell
docker build \
  -f workbench/environment/Dockerfile \
  -t workbench:dev \
  workbench/environment
```

## Schema and environment decisions

- `[environment].docker_image = "workbench:dev"`.
- Four stdio MCP server entries invoke installed argument-free wrappers.
- Audit tasks are intentionally seatless.
- No `[harness] max_tool_calls` or other hard call-budget field.
- Reference tool-path floors are metadata only.
- Agent network permits only the lifecycle gateway host during the agent phase.
- Verifier runs without network.
- Agent timeout is multiplied by 2.0 by the matrix runner after real GLM and
  DeepSeek trials proved 1,800 seconds insufficient.

## Staging and offstage security

`harbor_stage.py` performs these steps before the agent starts:

1. copy each fresh database to environment-owned mode-0700 state;
2. copy the cached MCP runtime to environment-owned storage;
3. install one no-argument wrapper for Gmail, Slack, iManage, and Clio;
4. install a no-argument reference wrapper used only by the solution phase;
5. delete staged databases, runtime source, and other internals from the shared
   task path;
6. leave only the intended agent workspace and public tool contract.

The wrappers use `#!/bin/sh -p` so the environment effective UID is retained.
Actual container tests confirm EUID 10000 when invoked by the agent, while the
agent cannot read databases/runtime, import staged modules, pass oracle
arguments, or execute arbitrary environment commands. The verifier can read an
agent-created mode-0640 deliverable.

## Reward Kit port

Each task has one answer dimension and one process dimension. Answer weights
sum to 100. Former exact-set fields allocate 90% of their field weight to
normalized Counter-F1 and 10% to exact certification. This provides useful
near-miss credit without rewarding shotgun extras or duplicate evidence.

The verifier boundary is intentionally strict:

- no-follow, regular-file, size-bounded deliverable loader;
- exact top-level and nested keys/types;
- bool rejected where integer is required;
- finite JSON only;
- bounded depth and defensive trajectory parsing;
- duplicate-aware, type-tagged canonicalization;
- malformed or missing deliverables score zero;
- JavaScript process detection excludes comments, strings, template raw text,
  and regex literals while retaining executable template interpolation and real
  unified-exec calls.

Reward Kit runs once, then `tests/test.sh` writes:

```json
{
  "reward": 1.0,
  "answer": 1.0,
  "process": 0.0
}
```

for every reference solution.

## Task truth refresh

- Standard drift retains its rule and certifies the four silent versions.
- Client departure retains the repaired email, termination, document, and
  Slack IDs.
- Operative deadline retains the five-reference reasoning chain.
- Second read certifies 75 requests, 12 lanes, 66 same-day responses, and 3
  unanswered requests.
- Vanished clause enforces registry-marker parity and the 36/32/31 corpus
  shape.
- Fee dispute returns five `unsupported_days` records without discarding any of
  the 47 affected entries.
- Billing hygiene returns three structured anomalous person-days and phantom
  note 176.
- Visitor log uses end-of-request-day custody, first qualifying return, and
  structured next-working-day/unresolved breaches.

## Provider runner

The gateway restores the stripped model alias, injects the exact provider order
and `allow_fallbacks=false`, and proxies Responses streams and error bodies
unchanged. It never logs request content, authorization headers, or exception
text. A custom Codex provider name forces local compaction because OpenRouter
does not implement Codex's `/responses/compact` extension.

Matrix fingerprints include git revision, image ID, task source, materialized
environment, gateway version, Harbor/Codex versions, custom agent, compaction
mode, timeout multiplier, model, and provider order. Existing job/report paths
are rejected before launch.

Credits are checked before, during, and after each launch. In-flight polling
runs every 30 seconds and cancels Harbor's dedicated process group if observed
cost exceeds the authorized forecast or touches the reserve. This closes the
duration-driven overrun found in the second-read evidence-ledger batch.

Fresh task generation also validates each `[metadata.evidence]` contract before
staging: the primary workpaper row count, optional nested source-ID count, and
joined product surfaces must match the fresh oracle. Canonical-byte comparison
still detects every value-level truth drift.

## Verification status

Completed:

- 9,427-event byte-identical history check;
- all eight fresh environments;
- eight reference solutions at full answer reward;
- synthetic answer/process/security regressions;
- actual Docker security probes;
- actual current-source offline Harbor 8/8 reference job
  `hartwell-oracle-current-20260811-3`;
- gateway lifecycle/provenance/budget tests;
- shared image build and workspace static/test gates.

Not completed because the continuation cap bound:

- the final five-task best-of-three hardness matrix;
- six cancelled second-read GLM/DeepSeek cells;
- eight model-based `harbor check` quality evaluations.

Static Harbor layout tests and actual Harbor execution pass; the unrun
model-based checks are explicitly not reported as passing.
