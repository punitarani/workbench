# Hartwell Harbor evaluation report

## Outcome

The Hartwell evaluation suite is implemented, deterministic, secure, and
reference-valid under Harbor. The requested paid 8-task matrix could not be
completed inside the immutable `$25.00` project cap. One task has a valid 3x3;
seven task batches were not launched and are not assigned scores.

This is a budget stop, not a model-quality conclusion. The required claim that
at least five tasks have best-of-three answer below `0.5` for all three models
is not established.

## Corpus and tools

- 9,427 deterministic events over the four-month world.
- 77 cached content pieces reused; zero new content-model calls.
- `build_history.py --days all --check`: 3,730,130 identical bytes.
- All eight bundles rematerialized with the current `rate_cents` and `billable`
  projectors.
- Public MCP tools: Gmail 4, Slack 9, iManage 9, Clio 8.
- Audit tasks remain intentionally seatless; the agent receives only the
  documented organization-level surfaces.

## Task results before paid evaluation

Every reference solution produced its deliverable and scored
`reward=answer=1.0`, with `process=0.0` as the expected diagnostic for a direct
oracle. Set criteria use 90% normalized Counter-F1 and 10% exact certification.
Malformed, missing, non-finite, wrong-typed, duplicated, deeply nested, and
symlinked submissions are covered by regression tests.

| Task | Answer truth summary | Floor | Naive |
|---|---|---:|---:|
| fee dispute | 7 disputed entries and five structured unsupported days | 49 | 0.6440 |
| client departure | repaired cross-surface departure record | 10 | 0.5340 |
| billing hygiene | 3 days / 18 entries / 876 minutes / 687,600 cents / note 176 | 146 | 0.2226 |
| second read | 75 requests / 12 lanes / 66 same-day / 3 unanswered | 54 | 0.5130 |
| visitor log | 71 requests / 59 timely / 10 late / 2 unresolved | 54 | 0.5356 |
| operative deadline | five-reference operative-date chain | 40 | 0.1753 |
| standard drift | four silent legal versions | 48 | 0.3738 |
| vanished clause | 36 total / 32 multi-version / 31 clean multi-version | 199 | 0.2152 |

## Harbor and routing implementation

- Harbor 0.18.0, Reward Kit 0.1.7, Codex 0.147.0.
- One `workbench:dev` image; no per-task Dockerfiles.
- Environment-owned mode-0700 databases and runtime; argument-free MCP and
  oracle wrappers; staged internals removed before the agent starts.
- Custom Responses provider `hartwell_gateway` forces Codex local compaction.
  This avoids OpenRouter's nonexistent `/responses/compact` route.
- Gateway restores aliases and injects the exact provider order with
  `allow_fallbacks=false`:
  - Luna: OpenAI.
  - GLM: Baidu FP8, Novita FP8, StreamLake FP8.
  - DeepSeek: Baidu FP8, GMI Cloud FP8, Baseten FP8.
- Actual selected provider is not exposed by the Responses stream; reports
  therefore distinguish enforced order from unknown actual provider.
- The OpenRouter key stays host-side. Containers receive a short-lived gateway
  token through a mode-0600 environment file that is deleted after launch.
- Request content, authorization headers, and transport exception text are not
  logged.

## Paid matrix evidence

The valid fee-dispute matrix used evaluation revision `8aaa868`, image
`sha256:aff89613a1e90b38f58782f86ff383293ca5c55f38f06eb6a1f1cb2e0be21052`,
gateway v2, and the provider routes above.

| Model | Attempt 1 | Attempt 2 | Attempt 3 | Best |
|---|---:|---:|---:|---:|
| Luna answer | 1.0000 | 1.0000 | 0.6920 | 1.0000 |
| Luna process | 1.0000 | 0.8333 | 0.8333 | 1.0000 |
| GLM answer | 0.8432 | 1.0000 | 0.8432 | 1.0000 |
| GLM process | 1.0000 | 0.7750 | 0.9083 | 1.0000 |
| DeepSeek answer | 0.6416 | 1.0000 | 0.9800 | 1.0000 |
| DeepSeek process | 0.8625 | 0.7500 | 0.7500 | 0.8625 |

No fee cell is an invalid trial. The fee task does not defeat any of the three
models under best-of-three.

## Invalid trials and repairs

Invalid trials were excluded throughout.

1. Run A used Codex's OpenAI remote-compaction path. OpenRouter rejected the
   compacted prompt with `invalid_prompt`; those cells are invalid.
2. Run B disabled the v2 feature but Codex v1 still called
   `/v1/responses/compact`, which OpenRouter does not implement. The custom
   provider name then forced local compaction.
3. Run C proved the custom provider with a valid Luna result, but GLM and
   DeepSeek hit the task's 1,800-second Harbor timeout while still gathering
   evidence. They were invalid, not zero-score answers.
4. A targeted recovery used the identical task/image/gateway/Codex/provider
   state with Harbor's 2x agent-time multiplier. GLM and DeepSeek completed
   validly.
5. The six additional fee attempts used the same corrected allowance and all
   completed validly.
6. Commit `dd6e11f` makes the 2x multiplier part of the command and fingerprint
   and scales metered observations to the next launch's cell count.

## Spend

Authoritative OpenRouter meter:

- baseline: `32.2139`;
- final: `56.005689513`;
- project spend: `$23.791789513`;
- remaining before cap: `$1.208210487`;
- launchable after `$1.50` reserve: `-$0.291789513`.

The runner therefore correctly forbids another batch. Seven unlaunched tasks
have no final matrix values.

## Verification completed

- Deterministic history and rematerialization gates.
- Eight full-reward references and all naive/floor checks.
- Synthetic verifier corpus: exact, near miss, shotgun, malformed, missing
  trajectory, duplicate evidence, deep JSON, symlink, and unified-exec cases.
- Actual Docker privilege/security probes.
- Actual offline Harbor reference job: 8/8 completed, no exceptions, full
  answer reward.
- Provider-gateway and matrix lifecycle tests.
- `workbench:dev` build at image
  `sha256:aff89613a1e90b38f58782f86ff383293ca5c55f38f06eb6a1f1cb2e0be21052`;
  this image powered the offline 8/8 job and paid cells. A later no-change
  rebuild retry was blocked before the first Dockerfile step by Docker's
  external frontend/daemon handoff.
- `uv sync`: clean.
- `uv run pytest`: 682 passed, 13 skipped, 1 deselected.
- `uv run ruff check .`: pass.
- `uv run ruff format --check .`: 308 files formatted.
- `git diff --check`: pass.
- Bun/TypeScript gates are not applicable: the workspace has no `package.json`,
  Bun tests, or `typecheck` script.

## Unresolved items

1. Rerun all eight 3x3 matrices from the current clean source revision after an
   explicit budget/cap change. Source hardening after `8aaa868` means the fee
   diagnostic cells must also be rerun for a single final fingerprint.
2. Establish or reject the five-task `<0.5` target from valid cells only.
3. Run Harbor's model-based `harbor check` on all eight tasks when a separate
   evaluator budget is authorized. Static layout tests and actual offline
   Harbor execution pass, but the default model-based check was not charged
   after the project cap became binding.
