# Hartwell Harbor evaluation report

## Outcome

The eight-task Hartwell suite is deterministic, securely staged, and
reference-valid. Its generation pipeline now certifies the retained evidence
population before Harbor staging, so stale or accidentally simplified task
worlds fail the build.

The requested hardness claim is not yet established. Two complete current-era
diagnostic matrices showed that the compact `standard-drift` and
`operative-deadline` answers remain too solvable. A later evidence-ledger run
proved `second-read-audit` below `0.5` for Luna on three valid attempts, but six
GLM/DeepSeek cells were cancelled when a severe in-flight cost overrun
threatened the explicit project reserve. Cancelled cells are invalid, not low
scores. No claim is made that five tasks defeat all three models.

## Corpus and task generation

- 9,427 deterministic events over four simulated months.
- 77 cached content pieces reused; zero new content-model calls.
- `build_history.py --days all --check`: 3,730,130 byte-identical bytes.
- All eight bundles rematerialized with the current `rate_cents` and `billable`
  projectors.
- Public MCP tools: Gmail 4, Slack 9, iManage 9, Clio 8.
- Tasks remain intentionally seatless and expose only the documented
  organization-level product surfaces.

`build_tasks.py` runs each restricted stdout oracle against its fresh bundle,
requires canonical bytes to match the committed oracle, checks a typed evidence
contract in `task.toml`, and stages only after both checks pass. The current
contracts certify:

| Task | Primary retained evidence | Certified population |
|---|---|---:|
| fee dispute | complete daily support workpaper | 22 days / 254 activity IDs / 28 communications |
| client departure | unanswered client correspondence | 4 emails |
| billing hygiene | complete billable person-day review | 655 rows / 4,233 activity IDs |
| second read | complete first-response audit | 75 requests |
| visitor log | complete custody audit | 71 requests |
| operative deadline | stale-setting citations | 5 communications |
| standard drift | post-v1 NDA version audit | 16 versions / 4 covering emails |
| vanished clause | post-v1 document revision audit | 57 revisions / 53 communications |

The standard-drift diagnostic also exposed a fairness defect: iManage serves
UTC timestamps while the oracle reports Pacific dates. The instruction now
states `America/Los_Angeles` explicitly and requires conversion; a regression
test prevents hidden timezone arithmetic from becoming artificial difficulty.

## Reference, baseline, and verifier quality

Every reference emits one stdout JSON object without modifying the workspace
and earns `reward=answer=1.0`; direct oracles correctly have `process=0.0`.
Current public-path floors and naive scores are:

| Task | Truth summary | Floor | Naive answer |
|---|---|---:|---:|
| fee dispute | 22 review days; 254 IDs; 28 support messages; 5 unsupported days | 49 | 0.6763 |
| client departure | repaired cross-surface departure record | 10 | 0.5340 |
| billing hygiene | 655 rows; 3 anomalous days; 18 entries; note 176 | 146 | 0.2226 |
| second read | 75 requests; 12 lanes; 66 same-day; 3 unanswered | 54 | 0.5130 |
| visitor log | 71 requests; 59 same-day; 10 next-day; 2 unresolved | 54 | 0.5356 |
| operative deadline | 3 supersessions; 5 stale communications | 40 | 0.1753 |
| standard drift | 9 NDAs; 16 post-v1 revisions; 4 silent versions | 48 | 0.3738 |
| vanished clause | 36 documents; 57 revisions; 31 clean multi-version files | 199 | 0.2152 |

Answer collections use 90% normalized Counter-F1 and 10% exact certification.
Headline-only and shotgun regressions remain below `0.5` for evidence-ledger
tasks, while typed near misses retain proportional credit. Loaders use
`O_NOFOLLOW`, `fstat` regular-file checks, byte bounds, finite/depth-safe JSON,
strict public schemas, and duplicate-sensitive canonicalization. Tests cover
symlinks to offstage truth, wrong scalar types, extra keys, non-finite values,
deep inputs, nested/outer duplicates, reordered sets, missing deliverables,
malformed trajectories, and mention-only unified-exec text.

The current fee task now retains the complete post-cutoff April support audit
that its public tool path was already constructing: 22 daily rows reconcile all
254 Meridian activities and the exact 2 Gmail plus 26 Slack support identities.
The five silent days remain a separately graded exception view. An otherwise
perfect submission that omits this retained workpaper scores `0.46`; the prior
compact fee matrices are therefore design diagnostics, not reusable cells for
the current task revision.

## Harbor and routing

- Harbor 0.18.0, Reward Kit 0.1.7, Codex 0.147.0.
- One `workbench:dev` image:
  `sha256:aff89613a1e90b38f58782f86ff383293ca5c55f38f06eb6a1f1cb2e0be21052`.
- Environment-owned mode-0700 state/runtime; privilege-preserving,
  argument-free MCP and oracle wrappers; staged internals removed before the
  agent starts.
- Local Responses gateway restores model aliases, injects exact provider order,
  and sets `allow_fallbacks=false`.
- The OpenRouter key stays host-side; containers receive a short-lived mode-0600
  gateway token. Request bodies, authorization headers, secrets, and raw
  exception text are never logged.
- Reports require Codex 0.147.0, finite `[0,1]` dimensions,
  `reward == answer`, no exception, exact per-model attempt counts, current task
  and materialized-environment hashes, and absent pre-existing job/report paths.

The actual provider selected by OpenRouter is not returned in the streamed
Responses result. Provenance therefore records enforced provider order and
labels actual provider as unknown rather than inventing precision.

## Paid diagnostic matrices

### Standard drift

Revision `b6dd1d3`, nine valid cells:

| Model | Attempt 1 | Attempt 2 | Attempt 3 | Best |
|---|---:|---:|---:|---:|
| Luna answer | 0.8544 | 0.8944 | 0.8944 | 0.8944 |
| GLM answer | 0.9094 | 0.9094 | 0.9094 | 0.9094 |
| DeepSeek answer | 0.9094 | 0.8944 | 0.8944 | 0.9094 |

All models built all 16 rows. The repeated miss was Harborlight v2's save date:
agents used the displayed UTC date while the oracle converted to Pacific. This
is a specification defect, not legitimate hardness, and is fixed in the current
instruction. The task remains genuinely too easy and does not count toward the
target.

### Operative deadline

Revision `b6dd1d3`, nine valid cells:

| Model | Attempt 1 | Attempt 2 | Attempt 3 | Best |
|---|---:|---:|---:|---:|
| Luna answer | 0.4633 | 0.8180 | 0.4633 | 0.8180 |
| GLM answer | 0.4633 | 0.4633 | 0.4633 | 0.4633 |
| DeepSeek answer | 1.0000 | 0.4633 | 0.8880 | 1.0000 |

The shared `0.4633` failure stopped at the second written continuance and missed
the later private Slack correction. Luna's `0.8180` found the operative date but
missed two stale email citations. DeepSeek's exact attempt reconstructed the
entire chain after roughly 30 minutes. The rule is sound, but the current scope
does not defeat Luna or DeepSeek under best-of-three.

### Second read

Current evidence-ledger task source, three valid Luna cells:

| Model | Attempt 1 | Attempt 2 | Attempt 3 | Best | Validity |
|---|---:|---:|---:|---:|---|
| Luna answer | 0.2886 | 0.2886 | 0.1219 | 0.2886 | 3/3 valid |
| GLM answer | — | — | — | — | 0/3; operator-cancelled |
| DeepSeek answer | — | — | — | — | 0/3; operator-cancelled |

The two `0.2886` Luna answers got every management summary and exception set
right but matched only 1 of 75 full audit rows. The `0.1219` answer also missed
part of the summary. This demonstrates that the ledger criterion captures the
retained work product rather than merely grading the headline.

The cancelled GLM/DeepSeek trajectories had enumerated all 75 requests but were
still reconciling response qualification, Gmail-vs-Slack precedence, and dates
after 37 minutes. They had no submitted deliverable and are not scores.

## Spend and in-flight repair

The continuation baseline was `64.274128970` with an additional `$25.00`
authorization. Final settled usage is `84.197153415`:

- continuation spend: `$19.923024445`;
- remaining before continuation cap: `$5.076975555`;
- launchable after reserve: `$3.576975555`.

The second-read batch exceeded its `$4.00` forecast and settled at
`$12.940024093`. It was stopped before the explicit reserve was consumed.
Commit `8e47e9c` adds 30-second in-flight credit polling and process-group
termination when observed cost exceeds the launch authorization or reaches the
reserve. No later paid work was launched.

## Verification evidence

- deterministic history rebuild and all-task fresh oracle certification;
- all eight full-reward reference solutions and measured MCP floors;
- synthetic answer/process verifier corpus across all eight tasks;
- actual Docker privilege/offstage-state probes;
- current-source offline Harbor reference job
  `hartwell-oracle-current-20260811-3`: 8/8 complete, no exceptions,
  `reward=answer=1`, `process=0`;
- provider-gateway alias, pin, fallback, streaming, error, logging, provenance,
  lifecycle, freshness, and budget tests;
- environment image build at the digest above;
- Python workspace tests: 782 passed, 13 skipped, 1 deliberately deselected;
- Ruff check/format and `git diff --check` gates.

## Unresolved items

1. The five-task best-of-three `<0.5` target is not established.
2. A new paid authorization is required before any further nine-cell batch.
   Resume from the settled meter and use at least `$12.9401` as the observed
   long-ledger worst case unless cheaper identical-protocol evidence supersedes
   it.
3. Cancelled second-read GLM/DeepSeek cells must be rerun; they cannot be merged
   with a future revision unless every stored fingerprint matches exactly.
4. The expanded fee workpaper requires a new paid 3x3; all earlier fee cells
   predate its current fingerprint.
5. Use model-based `harbor analyze`/`harbor check` only under a separately
   budgeted evaluator run. Deterministic criterion/trajectory inspection was
   used here because the remaining reserve was binding.
