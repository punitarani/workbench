# Harbor paid-diagnostic failure-mode analysis

Forensic reconstruction of every paid Harbor cell run against the Hartwell
suite on 2026-08-10 and 2026-08-11. No model spend was incurred to produce
this document. Nothing in `datasets/`, the graders, or the oracles was
modified.

## 0. Evidence provenance — read this first

**The Harbor trial directories for the paid diagnostics no longer exist on
disk.** All paid work ran inside a superpowers worktree at
`/Users/punit/.config/superpowers/worktrees/workbench/resume-hartwell-harbor-suite`,
writing to `<worktree>/jobs/`. That worktree directory is now empty (mtime
2026-08-11 08:14, matching commit `0965b90`), so every `result.json`,
`reward-details.json`, `agent/codex.txt`, `agent/trajectory.json`, and
`*-matrix.json` from those runs was removed with it. A Spotlight sweep for
`reward-details.json` and `trial.log` across the machine confirms only four
surviving Harbor trial directories, all `fee-dispute-reconstruction`, all from
2026-08-09, in `/Users/punit/projects/workbench/jobs/`:

| Job | Trial | Kind |
|---|---|---|
| `jobs/pilot-oracle` | `fee-dispute-reconstruction__kfvZrsa` | reference oracle |
| `jobs/pilot-codex-1` | `fee-dispute-reconstruction__TcTyXXK` | Codex pilot |
| `jobs/pilot-codex-2` | `fee-dispute-reconstruction__ceiuwBV` | Codex pilot |
| `jobs/2026-08-09__16-12-53` | `check-fee-dispute-reconstruction__oohxbP9` | harbor check |

The authoritative surviving record of the paid runs is the Codex orchestrator
rollout log:

```
/Users/punit/.codex/sessions/2026/08/09/rollout-2026-08-09T23-21-11-019fea55-1283-7430-8023-914c3b7476b7.jsonl
```

26.6 MB, 17,205 records, covering 2026-08-10T06:21:12Z through
2026-08-11T13:02:47Z. It contains 2,755 shell command/output pairs, including
the `jq` dumps of every `*-matrix.json`, the `reward-details.json` criterion
tables, and substantial excerpts of the agent trajectories, captured before
deletion. Every figure below is quoted from that log. Where a figure could not
be recovered it is marked `unrecoverable`, not estimated.

Two consequences:

1. `harbor analyze` can no longer be run on these trajectories. Any future
   trajectory-level work needs a fresh paid run.
2. The runner's default `jobs_dir` is `repository / "jobs"`
   (`adapters/src/workbench/adapters/harbor_matrix/cli.py:55`). Running the
   matrix from a disposable worktree therefore puts the entire paid evidence
   base inside a directory that worktree teardown destroys. This is itself a
   process failure worth fixing.

A second correction to the briefing: the paid diagnostics were **not three
tasks**. Seven distinct paid Harbor launches touched five tasks, plus a
`vanished-clause` 3x3 on 2026-08-10 that the briefing omits entirely, and
three later single-model screens under a further `$12.50` authorization that
postdate `CHECKPOINT.md`.

---

## 1. Inventory

`answer` is canonical reward (`reward == answer`); `process` is diagnostic
only. Cancelled and timed-out cells are **not scores** and are excluded from
every best-of-three claim.

### 1a. `vanished-clause` 3x3 — `hartwell-hardness-20260810-vanished-1`

Batch marked **invalid** by the runner (`Harbor batch has 1 invalid trials`).
Settled `$8.268439457` (`56.005689513` → `64.274128970`), forecast `$8.00`.

| Trial | Model | Answer | Process | Stop reason | MCP calls | Notes |
|---|---|---:|---:|---|---:|---|
| `vanished-clause__kFnrfzi` | Luna | 1.0000 | 1.0000 | ok | 321 | |
| `vanished-clause__wiuFApX` | Luna | 0.8440 | 1.0000 | ok | 552 | |
| `vanished-clause__eqwsZob` | Luna | 0.8350 | 1.0000 | ok | 381 | |
| `vanished-clause__CgoSmrp` | GLM | 1.0000 | 0.8333 | ok | 181 | |
| `vanished-clause__GPhUdjE` | GLM | 1.0000 | 0.7222 | ok | 260 | |
| `vanished-clause__fjvmKRq` | GLM | 1.0000 | 1.0000 | ok | 199 | |
| `vanished-clause__nBmhuGz` | DeepSeek | 1.0000 | 1.0000 | ok | 266 | |
| `vanished-clause__3qmnUX3` | DeepSeek | 0.8688 | 1.0000 | ok | 357 | |
| `vanished-clause__5DHRhwV` | DeepSeek | — | — | **AgentTimeoutError** (3600 s) | 383 | **INVALID — not a score** |

Best-of-three (valid cells only): Luna 1.0000, GLM 1.0000, DeepSeek 1.0000.

### 1b. `standard-drift` 3x3 — `hartwell-hardness-20260811-standard-1`

Revision `b6dd1d3`, Harbor 0.18.0, Codex 0.147.0, 9/9 valid. Launched
07:21:03Z, report written 07:47:56Z (~27 min wall for the batch at
concurrency 8). Immediate metered `$3.151754`; settled `$3.412067`
(`64.274128970` → `67.686196267`).

| Trial | Model | Attempt | Answer | Process | Stop | `codex.txt` bytes |
|---|---|---:|---:|---:|---|---:|
| `standard-drift__RLvPyhB` | Luna | 1 | 0.8544 | 1.0000 | ok | 1,198,960 |
| `standard-drift__UNrXyBX` | Luna | 2 | 0.8944 | 0.8667 | ok | 757,888 |
| `standard-drift__cQc8H49` | Luna | 3 | 0.8944 | 1.0000 | ok | 995,887 |
| `standard-drift__R2Ywb5d` | GLM | 1 | 0.9094 | 0.8667 | ok | 294,929 |
| `standard-drift__iFjVPma` | GLM | 2 | 0.9094 | 0.8000 | ok | 217,338 |
| `standard-drift__nC353XM` | GLM | 3 | 0.9094 | 0.8000 | ok | 196,150 |
| `standard-drift__8pa2gSu` | DeepSeek | 1 | 0.9094 | 1.0000 | ok | 238,041 |
| `standard-drift__PMcz9Tu` | DeepSeek | 2 | 0.8944 | 0.8000 | ok | 402,967 |
| `standard-drift__sYNiGzS` | DeepSeek | 3 | 0.8944 | 0.8667 | ok | 421,663 |

Best-of-three: Luna 0.8944, GLM 0.9094, DeepSeek 0.9094. Exact per-trial MCP
call counts are `unrecoverable`; the orchestrator recorded one cell as having
"completed 123 tool calls" at the 27-minute mark (L11596).

### 1c. `operative-deadline` 3x3 — `hartwell-hardness-20260811-operative-1`

Revision `b6dd1d3`, 9/9 valid. Launched 07:51:41Z, report 08:24:37Z (~33 min).
Settled `$3.570933` (`67.686196267` → `71.257129322`). Agent phase timeout
1800 s x 2.0 multiplier = 3600 s effective.

| Trial | Model | Attempt | Answer | Process | Stop | Approx. wall |
|---|---|---:|---:|---:|---|---|
| `operative-deadline__Qo2ioU7` | Luna | 1 | 0.4633 | 0.8750 | ok | < 4 min |
| `operative-deadline__kPYF6oU` | Luna | 2 | 0.8180 | 0.8750 | ok | ~12 min |
| `operative-deadline__r8idFJm` | Luna | 3 | 0.4633 | 0.8750 | ok | < 12 min |
| `operative-deadline__XVjDbJT` | GLM | 1 | 0.4633 | 0.8750 | ok | ~20 min |
| `operative-deadline__yfwJisW` | GLM | 2 | 0.4633 | 0.8750 | ok | ~20 min |
| `operative-deadline__8z3gtJw` | GLM | 3 | 0.4633 | 0.8750 | ok | ~32 min |
| `operative-deadline__bJ9EEJy` | DeepSeek | 1 | 0.4633 | 0.8750 | ok | ~14 min |
| `operative-deadline__xQSdv7Z` | DeepSeek | 2 | 0.8880 | 0.8750 | ok | ~30 min |
| `operative-deadline__aoaKxYP` | DeepSeek | 3 | 1.0000 | 0.8750 | ok | ~30 min |

Best-of-three: Luna 0.8180, GLM 0.4633, DeepSeek 1.0000. Wall times are
derived from `docker ps` uptime snapshots in the log, not from `result.json`
timestamps, which are `unrecoverable`.

### 1d. `second-read-audit` 3x3 — `hartwell-final-20260811-second-1`

Evidence-ledger task source. Launched ~08:37Z. **3/9 valid.** Settled
`$12.940024093` against a `$4.00` forecast — the overrun that closed the
continuation ledger.

| Trial | Model | Answer | Process | Stop | Trajectory at stop |
|---|---|---:|---:|---|---|
| `second-read-audit__G5i7nvk` | Luna | 0.2886 | 1.0000 | ok | submitted |
| `second-read-audit__drGUfAn` | Luna | 0.2886 | 1.0000 | ok | submitted |
| `second-read-audit__8mzC82r` | Luna | 0.1219 | 1.0000 | ok | submitted |
| `second-read-audit__2byanP5` | GLM | — | — | **CancelledError** | 636 codex lines, last item `mcp_tool_call` |
| `second-read-audit__DowbBGU` | GLM | — | — | **CancelledError** | 202 lines, last item `agent_message` |
| `second-read-audit__s35iAKo` | GLM | — | — | **CancelledError** | 319 lines, last item `agent_message` |
| `second-read-audit__Rz68ibA` | DeepSeek | — | — | **CancelledError** | 775 lines, last item `mcp_tool_call` |
| `second-read-audit__V9wRmjJ` | DeepSeek | — | — | **CancelledError** | 272 lines, last item `command_execution` |
| `second-read-audit__gr7HwFJ` | DeepSeek | — | — | **CancelledError** | 273 lines, last item `mcp_tool_call` |

Best-of-three: Luna 0.2886. **GLM and DeepSeek have no score for this task.**
All six were killed at ~37 minutes of a 60-minute effective allowance when a
manual meter check showed `$11.94` in flight against a `$4.00` authorization.
None had written a deliverable.

### 1e. Post-checkpoint screens under the further `$12.50` authorization

These postdate `CHECKPOINT.md` and are absent from `REPORT.md`.

| Run | Task | Trial | Model | Answer | Process | Stop |
|---|---|---|---|---:|---:|---|
| `hartwell-hardness-20260811-fee-ledger-1` | fee dispute (22-day workpaper) | `fee-dispute-reconstruction__mYGht99` | Luna | 1.0000 | 0.8333 | ok |
| | | `fee-dispute-reconstruction__krL9vLN` | GLM | — | — | **CancelledError** |
| | | `fee-dispute-reconstruction__dAtUrPm` | DeepSeek | — | — | **CancelledError** |
| `hartwell-hardness-20260811-billing-screen-1` | billing hygiene | `billing-hygiene-audit__v5Yhzkb` | Luna | 1.0000 | 1.0000 | ok |
| | | `billing-hygiene-audit__Xmwcfwb` | GLM | — | — | **CancelledError** |
| | | `billing-hygiene-audit__E7RHhq4` | DeepSeek | — | — | **CancelledError** |
| `hartwell-hardness-20260811-visitor-screen-1` | visitor log | `visitor-log-audit__FX4P7JE` | Luna | 0.2793 | 1.0000 | ok |
| | | `visitor-log-audit__agvwSGs` | GLM | — | — | **CancelledError** at `$4.6526` vs `$4.50` |
| | | `visitor-log-audit__empf3X9` | DeepSeek | — | — | **CancelledError** |
| `hartwell-real-ts-visitor-luna-1` | visitor log @ `b5b8102` | `visitor-log-audit__RWefLhG` | Luna | 0.3070 | 0.9286 | ok, later **invalidated** by discovered oracle defect |
| `hartwell-dst-visitor-luna-1` | visitor log @ `72f21cc` | `visitor-log-audit__ihy44wj` * | Luna | **1.0000** | 0.9286 | ok, `$0.032519` |

\* recorded only in container-name form (`visitor-log-audit__ihy44wj__env-main-1`); the trial directory's exact casing is `unrecoverable`.

The last row is the single most important number in this entire corpus. See
§4 and §5.

### 1f. Aggregate

| | Cells launched | Valid | Invalid |
|---|---:|---:|---:|
| `vanished-clause` | 9 | 8 | 1 (timeout) |
| `standard-drift` | 9 | 9 | 0 |
| `operative-deadline` | 9 | 9 | 0 |
| `second-read-audit` | 9 | 3 | 6 (budget cancel) |
| fee / billing / visitor screens | 9 | 3 | 6 (budget cancel) |
| repaired visitor screens | 2 | 2 | 0 (1 later invalidated by oracle defect) |
| **Total** | **47** | **34** | **13** |

---

## 2. Per-field breakdown

### 2a. `standard-drift` — 26 criteria, `version_audit` carries 58%

Weights from `tests/ground_truth.json`: `version_audit` 0.58 (0.522 F1 /
0.058 certified), `nda_survey` 0.09, `version_aggregates` 0.07,
`silent_versions` 0.06, `audit_reconciliation` 0.03, `format` 0.03,
`playbook_path` 0.02, and the six clause sub-fields at 0.005–0.015 each.

Criterion tables recovered for one trial per model:

| Criterion | Luna `RLvPyhB` (0.8544) | GLM `R2Ywb5d` (0.9094) | DeepSeek `8pa2gSu` (0.9094) |
|---|---:|---:|---:|
| `field_equals:drift.json` | 1.0 | 1.0 | 1.0 |
| `ndas.f1` / `.certified` | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| `silent_versions.f1` / `.certified` | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| `term.standard` / `.practice` | 1.0 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| `term.document` / `.version` / `.date` | **0.0 / 0.0 / 0.0** | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| `residuals.standard` | 1.0 | 1.0 | 1.0 |
| `residuals.practice` | **0.0** | 1.0 | 1.0 |
| `residuals.document` / `.version` / `.date` | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 | 1.0 / 1.0 / 1.0 |
| all 7 aggregates | 1.0 | 1.0 | 1.0 |
| `covering_email_count` | 1.0 | 1.0 | 1.0 |
| **`version_audit.f1`** | **0.9375** | **0.9375** | **0.9375** |
| **`version_audit.certified`** | **0.0** | **0.0** | **0.0** |
| `version_audit_reconciles` | 1.0 | 1.0 | 1.0 |
| `deliverable_format` | 1.0 | 1.0 | 1.0 |

The arithmetic closes exactly:

- `0.9094 = 1 − (0.522 × 0.0625) − 0.058`. **Every 0.9094 cell missed nothing
  except one row of the 16-row schedule.**
- `0.8944 = 0.9094 − 0.015`: one additional 0.015-weight clause sub-field.
- `0.8544 = 0.9094 − 0.015 − 0.015 − 0.010 − 0.015`
  (`term.document`, `term.version`, `term.date`, `residuals.practice`).

**The single field nobody gets is `version_audit.certified`, and the single
row nobody gets right is Harborlight v2 (`LEGAL!30.2`).** Oracle says
`2026-05-06`; all nine cells wrote `2026-05-07`. Because 15/16 rows were
right, `version_audit.f1` pinned at 0.9375 across all three model families —
a signature of a specification defect, not model variance. iManage exposed
save timestamps in UTC; the oracle converted to the firm's Pacific calendar;
the instruction never said so.

Everything else — the nine-file `conforms`/`deviates` certification, the four
silent versions, all seven aggregates, the four covering email IDs, the
`substantive`/`notices_only`/`unchanged` partition — was exact in every cell
of every model.

### 2b. `operative-deadline` — one field is 56% of the score

Weights, from the recovered `reward-details.json`: `operative_date` 10,
`operative_time` 4, `correction_ts` 7, `ordered_similarity` (superseded_dates)
8, `supersessions.f1` 9, `.certified` 1, **`stale_calendar_refs.f1` 50.4**,
`.certified` 5.6, `deliverable_format` 5. Total 100.

| Criterion | `Qo2ioU7` (0.4633) | `kPYF6oU` (0.8180) | `aoaKxYP` (1.0000) |
|---|---:|---:|---:|
| `operative_date` | 0.0 | 1.0 | 1.0 |
| `operative_time` | 0.0 | 1.0 | 1.0 |
| `correction_ts` | 0.0 | 1.0 | 1.0 |
| `superseded_dates` ordered similarity | 0.6667 | 1.0 | 1.0 |
| `supersessions.f1` / `.certified` | 0.8 / 0.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| **`stale_calendar_refs.f1`** | **0.5714** | **0.7500** | **1.0** |
| **`stale_calendar_refs.certified`** | 0.0 | **0.0** | 1.0 |
| `deliverable_format` | 1.0 | 1.0 | 1.0 |

Decoded against the five-item ground-truth set:

- `Qo2ioU7` (Luna, and the shared 0.4633 shape across all three families)
  wrote `operative_date: 2026-06-18` and two stale refs
  (`msg-000289`, `6431100.002256`). Precision 1.0, recall 0.4 → F1 0.5714.
  It stopped at the second **written** continuance and never found the Slack
  correction.
- `kPYF6oU` (Luna 0.8180) wrote `2026-06-25`, the right `correction_ts`
  `8767500.002917`, the complete supersession chain, and three stale refs.
  Precision 1.0, recall 0.6 → F1 0.75. It **deliberately excluded**
  `msg-000600` and `msg-000617`.
- `aoaKxYP` (DeepSeek 1.0000) wrote the same headline and all five refs,
  including `msg-000600` and `msg-000617`.

**The field that separates 0.4633 from 0.8180 is `correction_ts` plus the
headline block. The field that separates 0.8180 from 1.0000 is exactly two
Gmail IDs in `stale_calendar_refs`.** Nothing else in the task discriminates.
`deliverable_format` was 1.0 in all nine cells.

`process` was **0.8750 in all nine cells** — every model earned
`read_clerk_notices`, `resolved_matter_number`, `checked_private_correction`,
and `turn_efficiency`, and every model missed `checked_stale_chat` (weight 2
of 16, "agent invoked `slack_search_public`"). Nobody called the
public-only Slack search; they all used
`slack_search_public_and_private`, which is a strictly better tool. This
process criterion measures a tool name, not a behaviour.

### 2c. `second-read-audit` — the ledger is 72% and nobody built it

| Criterion | Weight | Luna `G5i7nvk` (0.2886) |
|---|---:|---:|
| `requests_reviewed` | 1.0 | 1.0 |
| `conversations_reviewed` | 1.0 | 1.0 |
| `unanswered_request_ts.f1` / `.certified` | 4.5 / 0.5 | 1.0 / 1.0 |
| `unanswered_requests.f1` / `.certified` | 3.6 / 0.4 | 1.0 / 1.0 |
| `answered_same_day` | 1.0 | 1.0 |
| `answered_next_working_day` | 1.0 | 1.0 |
| `unanswered_by_deadline` | 1.0 | 1.0 |
| `came_back_later.f1` / `.certified` | 2.7 / 0.3 | 1.0 / 1.0 |
| `unanswered_askers.f1` / `.certified` | 1.8 / 0.2 | 1.0 / 1.0 |
| **`response_audit.f1`** | **64.8** | **0.0133** |
| **`response_audit.certified`** | **7.2** | **0.0** |
| `response_audit_reconciles` | 6.0 | 1.0 |
| `deliverable_format` | 3.0 | 1.0 |

`0.2886 = 0.19 + 0.0133 × 0.648 + 0.06 + 0.03`. **Luna got every management
conclusion exactly right — all 75 request counts, all 12 lanes, all three
unanswered requests with exact timestamps and askers, every aggregate — and
matched 1 of 75 evidence rows.** `response_audit_reconciles` was 1.0, so the
ledger it did submit was internally consistent; it simply was not the right
ledger. This is the cleanest separation of conclusion quality from retained
work product anywhere in the corpus.

`8mzC82r` (0.1219) additionally lost part of the summary block. Criterion
detail for that cell is `unrecoverable`.

### 2d. `visitor-log-audit` — same shape, and then a reversal

`FX4P7JE` (Luna 0.2793): every aggregate and all 12 breach partitions exact;
`custody_audit` F1 = **0.0141** (1 of 71 rows). `RWefLhG` (0.3070 at
`b5b8102`): the orchestrator's decomposition found "Luna derived every
request, breach, outcome, and source ID correctly, but used the legally
appropriate `America/Los_Angeles` DST offsets. The oracle still emitted a
fixed `-08:00`, causing **67/71 otherwise-correct ledger rows to fail exact
matching after March 8**." After `72f21cc` made the oracle DST-aware and made
the verifier compare *instants* rather than offset strings, the same model on
the same task scored **1.0000**.

---

## 3. Trajectory analysis

Per-tool MCP counts survive in full only for `vanished-clause` and the billing
screen; for the other tasks only trajectory sizes and narrative excerpts
survive.

### 3a. `vanished-clause` — winning vs losing paths, quantified

| Trial | Model | Answer | MCP calls | Dominant tools | In-tok / out-tok |
|---|---|---:|---:|---|---|
| `kFnrfzi` | Luna | **1.0000** | 321 | `get_document_versions` 131, `download_document` 87, `slack_search_public` 68, `search_threads` 22 | 1.07 M / 12 k |
| `wiuFApX` | Luna | 0.8440 | 552 | `get_document_versions` 169, `download_document` 94, **`slack_search_public` 245** | 1.43 M / 19 k |
| `eqwsZob` | Luna | 0.8350 | 381 | `get_document_versions` 109, `download_document` 96, **`slack_search_public` 144**, `search_threads` **17** | 2.09 M / 18 k |
| `fjvmKRq` | GLM | **1.0000** | 199 | `search_threads` 54, `slack_search_public` 72, `get_document_versions` 33, `download_document` 18 | 4.14 M / 57 k |
| `CgoSmrp` | GLM | **1.0000** | 181 | `search_threads` 48, `slack_search_public` 53, `imanage.search` 12, `slack_search_public_and_private` 12 | 8.10 M / 83 k |
| `nBmhuGz` | DeepSeek | **1.0000** | 266 | `download_document` 84, `slack_search_public` 66, `search_threads` 50 | 8.54 M / 356 k |
| `3qmnUX3` | DeepSeek | 0.8688 | 357 | `download_document` 98, `search_threads` 75, `get_document_versions` 72, `slack_search_public` 60 | 12.84 M / 277 k |
| `5DHRhwV` | DeepSeek | invalid | 383 | `search_threads` 88, `slack_search_public` 84, `get_document_versions` 73 | 10.22 M / 331 k |

The pattern is unambiguous and it is **not** "more search wins":

- **The three perfect Luna/GLM/DeepSeek runs used the *fewest* calls**
  (321 / 199 / 266). The 0.8440 and 0.8350 Luna runs used 552 and 381.
- Every non-exact valid cell lost points **only** on
  `unreviewed_revisions` — the communication-reconciliation set — at F1
  0.5000, 0.5333, and 0.6250 with `certified` 0.0.
- The losing Luna runs are distinguished by a **Slack-heavy, Gmail-light**
  mix: `wiuFApX` made 245 `slack_search_public` calls against 31
  `search_threads`; `eqwsZob` made 144 against 17. The winning `kFnrfzi` made
  68 against 22, and the winning GLM runs made *more* Gmail calls than Slack
  ones relative to their totals. The reconciliation rule is Gmail-based; the
  losers substituted Slack breadth for the Gmail-per-day check and paid for
  it in exactly the field that rule governs.
- DeepSeek's timeout cell had a normal call profile (383) but 331 k output
  tokens. It did not stall on tools; it stalled generating.

### 3b. `operative-deadline` — the decisive divergence, in the models' own words

The three recovered trajectories differ at one reasoning step: **whether the
Slack `ts` can be ordered against Gmail dates at all.**

`aoaKxYP` (DeepSeek, 1.0000) hit the problem head-on and worked around it:

> "Now the critical question: does Grace's correction at `8767500` fall before
> or after these June 18-citing messages? The timestamp `8767500` maps (with a
> plausible epoch) to ~April 12, but that's clearly wrong — all the Gmail
> dates are 2026. Let me nail the actual calendar order using all the Slack
> context anchors."

It then reconstructed the calendar order from message content and submitted
all five stale refs.

`kPYF6oU` (Luna, 0.8180) reached the opposite conclusion and stated it
explicitly:

> "The June 18 emails/recap were sent before the final Slack move and
> therefore remain current-at-send, so they do not belong in
> `stale_calendar_refs`."

That is a chronology inversion, and it is the *entire* 0.182 gap. It is not a
rule misunderstanding — the model applied the stated rule correctly to a
timeline it could not order.

`Qo2ioU7` (Luna, 0.4633) never got that far; it wrote
`operative_date: 2026-06-18` and stopped at the written record.

Tooling friction is visible in all three: every one of them tried
`jq . deadline.json` and got `jq: command not found` (exit 127) before falling
back to `sed`, `node -e`, or `python3 -c`.

### 3c. `second-read-audit` — six cancelled trajectories, all in the same trap

At cancellation none of the six had a deliverable, and all had completed
enumeration. Their last agent messages localize the failure precisely:

- `2byanP5` (GLM, 636 lines): had classified all 75 and was doing a
  Gmail-vs-Slack precedence sweep — "No Gmail responses from asked_of to
  asked_by for any of the 5 unanswered requests. Now let me broaden the
  search…"
- `Rz68ibA` (DeepSeek, 775 lines): "The transcript has gaps — three requests
  are missing. Let me re-read the missing windows." Paginated re-reads.
- `V9wRmjJ` (DeepSeek, 272 lines): **stuck entirely on the timestamp epoch** —
  "The base date 2026-03-01 (either UTC or Pacific) gives no Friday requests,
  which contradicts the narrative… Let me check which requests fall on Fridays
  across ALL plausible bases."
- `DowbBGU`, `s35iAKo`, `gr7HwFJ`: all pivoting to "write a comprehensive
  Python script" / "read targeted windows" to beat the token cost of full
  channel reads. `gr7HwFJ` went further and probed the container filesystem
  for the backing databases (`find / -name "*.db" -o -name "*slack*"`).

Luna, by contrast, finished in 4–9 minutes by **not** attempting the ledger:
it answered the summary and submitted a near-empty `response_audit`. Its
process score was 1.0. So on this task the fast, high-process, low-cost path
is the low-scoring one, and the six models that were doing the actual work
were killed for cost.

### 3d. Code execution

Codex ran with `--enable unified_exec`. The models used it heavily and
successfully: the fee-ledger Luna cell (`mYGht99`, 1.0000) shows only **20
trajectory steps / 16 `exec` calls**, having pulled data through MCP and then
computed in-process. The billing Luna cell (`v5Yhzkb`, 1.0000) shows **173 MCP
calls — 89 `clio.list_activities`, 60 `slack.slack_read_channel`, 11
`gmail.search_threads` — and one `command_execution`**, with reasoning that is
explicitly a program-synthesis plan: "I plan to batch the calls in chunks of
about 20 parallel requests using `Promise.all`… store the data persistently in
a compact JSON format."

That is the decisive observation about these two tasks: **a model that can
write a paginating client turns a 655-row certification into a deterministic
join and scores exactly 1.0.**

---

## 4. Cause classification

One cause per non-perfect valid cell. Cancelled/timeout cells are classified
for completeness but carry no score.

### `standard-drift` — all 9 cells

**(D) instruction failure**, for the `version_audit` component in all nine.

Evidence: identical `version_audit.f1 = 0.9375` and
`version_audit.certified = 0.0` across three unrelated model families; the
disagreement is a single row, Harborlight `LEGAL!30.2`, oracle `2026-05-06`
vs. submitted `2026-05-07`. The instruction as run said only "`date`:
`<YYYY-MM-DD save date>`" and gave no timezone. The orchestrator reached the
same conclusion at L11667 — "its only consistent miss comes from an unstated
UTC-to-Pacific date conversion" — and the fix is a pure instruction change
(`72f21cc` adds "All `YYYY-MM-DD` values use the firm's Pacific calendar
(`America/Los_Angeles`). iManage exposes save timestamps in UTC, so convert
those timestamps to Pacific time before assigning a version to a calendar
day."), plus regression test
`test_instruction_declares_the_firm_calendar_timezone`.

The residual clause-block misses in `RLvPyhB` (0.8544) and the three 0.8944
cells are **(F) model capability** — a 0.015-weight sub-field naming which
document/version first departed on a clause, with the correct answer present
in the record and found by six of nine cells.

### `operative-deadline` — 8 non-perfect cells

Six cells at 0.4633 (Luna x2, GLM x3, DeepSeek x1): **(F) model capability.**
The instruction explicitly says "Do not stop at the court's written notices,
and do not assume the most recent internal mail is current: check everything
the firm wrote afterward." These cells stopped at `msg-000430` and never
searched Slack for a later correction. `Qo2ioU7`'s own summary — "Operative
hearing: June 18, 2026 at 10:00. Superseded settings: April 28 and May 20" —
shows it believed it was done. This is a planning/termination error against a
clear instruction.

`kPYF6oU` (Luna 0.8180): **(B) environment/tool obstruction.** The model found
everything except two Gmail IDs, and its stated reason for excluding them is a
timeline claim it could not verify: "The June 18 emails/recap were sent before
the final Slack move." At revision `b6dd1d3` the Slack `ts` was
`<simulation-relative seconds>.<counter>`, not a Unix instant — see
`tools/src/workbench/tools/slack/project.py` before `db07e87`, which emitted
`ts=f"{int(event.time)}.{len(messages):06d}"`. There was no sound way to order
`8767500.002917` against `2026-06-12`. The winning DeepSeek cell said so
outright. A criterion worth 56% of the answer was gated on a chronology the
environment did not expose.

`xQSdv7Z` (DeepSeek 0.8880): **(B)**, same mechanism, one ref short
(F1 0.8889 = 4/5).

`5DHRhwV` — n/a, different task; see below.

The `process = 0.875` shortfall in all nine is **(E) grader mismatch** on the
diagnostic dimension: `checked_stale_chat` requires `slack_search_public`, and
every model used the strictly-superior `slack_search_public_and_private`. It
does not affect `answer` and so does not affect reward, but it makes `process`
un-earnable by a competent agent.

### `second-read-audit`

Luna 0.2886 x2: **(A) genuine difficulty.** The instruction is explicit that
`response_audit` must contain one row per request; the model built the
correct conclusions, correctly reconciled what it submitted
(`response_audit_reconciles = 1.0`), and chose not to enumerate. Partial
credit was available and proportional. Nothing obstructed it.

Luna 0.1219: **(A)**, with an additional summary error; detail
`unrecoverable`.

Six GLM/DeepSeek cells: **(C) budget/turn exhaustion.** Explicitly
operator-cancelled at ~37 min of a 60-min allowance. The trajectories show
active MCP work at the moment of the kill. These are not scores and must
never be reported as such.

Note the contaminating factor: `V9wRmjJ`'s trajectory is dominated by the same
synthetic-epoch problem as `operative-deadline` (**B**), so even a completed
run at this revision would have been partly measuring a tooling artifact.

### `vanished-clause`

`wiuFApX` 0.8440, `eqwsZob` 0.8350, `3qmnUX3` 0.8688: **(A) genuine
difficulty.** All three lost points only on `unreviewed_revisions`, the
Gmail-per-day reconciliation set; five of eight valid cells got it exactly,
including one cell from each model family. The failing runs searched *more*
and searched the *wrong surface*.

`5DHRhwV` DeepSeek: **(C)**, `AgentTimeoutError` after 3600 s. Not a score.

### Visitor / fee / billing screens

`FX4P7JE` 0.2793 and `RWefLhG` 0.3070: **(E) grader mismatch**, and this one
is proven rather than argued. The orchestrator's decomposition found Luna
"derived every request, breach, outcome, and source ID correctly" but rendered
DST-correct local times while the oracle emitted fixed `-08:00`, failing
67/71 rows on string comparison. After `72f21cc` made the oracle DST-aware and
the verifier instant-comparing, **the same model on the same task scored
1.0000**. A 0.2793→1.0000 swing attributable entirely to timestamp
representation is the largest single measurement error in the corpus.

Six cancelled screen cells: **(C)**, but for two distinct reasons, both of
which must be recorded as "no score":

- **Methodological early-stop (4 cells).** The `fee-ledger-1` GLM/DeepSeek
  pair and the `billing-screen-1` GLM/DeepSeek pair were cancelled by the
  operator *because Luna had already scored 1.0000*, which mathematically
  disqualifies the task from a best-of-three-under-0.5 target: "no additional
  fee attempt can make this task qualify. I'm stopping the remaining fee
  smoke/continuation now to preserve budget, marking unfinished cells
  invalid" (L14324). Correct decision; still not evidence about GLM or
  DeepSeek.
- **Budget guard (2 cells).** The `visitor-screen-1` GLM/DeepSeek pair were
  terminated automatically at `$4.6526` against a `$4.50` authorization
  (L15012) — the guard added by `8e47e9c` working as designed. Both were
  making substantive MCP progress at the kill: "GLM found all 71 requests but
  is stuck organizing paginated lane histories; DeepSeek repeatedly widened
  scope" (L14940).

`mYGht99` and `v5Yhzkb` at 1.0000: not failures, but the most consequential
finding — see §5.

### Summary

| Cause | Valid non-perfect cells |
|---|---:|
| (A) genuine difficulty | 6 |
| (B) environment/tool obstruction | 2 |
| (C) budget/turn exhaustion or operator stop | 13 *(invalid, unscored: 1 timeout, 8 budget cancellations, 4 methodological early-stops)* |
| (D) instruction failure | 9 *(the `version_audit` component of every standard-drift cell)* |
| (E) grader mismatch | 2 *(+ the `process` dimension of all 9 operative cells)* |
| (F) model capability | 10 |

Read that table carefully. Of the paid cells that produced a below-1.0 answer,
**only six are unambiguously about the task being hard.** The rest are
tooling, timezone, instruction, and budget.

---

## 5. Why `standard-drift` and `operative-deadline` are easy

### `standard-drift`: the evidence is enumerable and the classification is mechanical

The task is a closed-world walk with no search problem at all.

1. **The population is bounded and self-announcing.** Nine NDAs under one
   iManage folder, each with 2–3 versions. `get_container_children` once, then
   `get_document_versions` nine times, then `download_document` sixteen times.
   Every model completed this. `versions_reviewed = 16` was exact in 9/9
   cells.
2. **The hard-sounding classification is a byte diff.** The instruction
   defines it operationally: `unchanged` = "byte-identical to the prior
   version"; `notices_only` = "removing the Notices section makes the two
   versions identical"; `substantive` = otherwise. That is a three-line
   program, not a judgement. The `substantive`/`notices_only`/`unchanged`
   partition was exact in 9/9 cells.
3. **The covering-email check is a single-key lookup.** "any email sent the
   same calendar day that names that vendor or carries that NDA file." One
   `gmail.search_threads` per vendor. `covering_email_count = 4` was exact in
   9/9 cells.
4. **The decoys don't bite.** The instruction pre-announces every trap: the
   next-day Summit email, the wrong-vendor Archway email, the Slack-not-email
   rule, the notices-only Brightwater diff. Warning an agent about a trap
   removes the trap.
5. **Consequently the whole 26-criterion rubric collapsed to one row.** All
   three models scored 1.0 on 24 of 26 criteria in every attempt. The two
   they missed were the same two, for the same non-substantive reason.

The floor is 48 public calls. Every model cleared it comfortably in ~10–27
minutes. **There is no step in this task where a model can be wrong for an
interesting reason.**

### `operative-deadline`: one search away, and the classification defaults

1. **The answer is a five-item chain reachable by one Slack search.** The
   whole difference between 0.4633 and 0.8180+ is finding
   `8767500.002917` — Grace's message "clerk just called about 00008 — moved
   again, the 25th at 9, not the 18th". A single
   `slack_search_public_and_private` on the matter number returns it. Three
   of nine cells found it; the other six simply never looked past Gmail.
2. **The evidence is concentrated in one matter.** `list_matters` →
   `00008-ArroyoConstruction` → every relevant Gmail thread and Slack message
   mentions Arroyo. There is no cross-matter disambiguation load beyond the
   one "other matters moved that season too" decoy, which the instruction
   again pre-announces.
3. **The classification defaults to the safe answer.** `stale_calendar_refs`
   is scored by F1, so a model that lists only the refs it is sure of gets
   precision 1.0 and pays only in recall. All three score levels
   (0.5714 / 0.75 / 1.0) are precision-1.0 answers with 2, 3, and 5 items.
   **No cell in the entire batch ever submitted a false positive.** The task
   never punishes under-claiming hard enough to force a decision.
4. **The deliverable is nine scalars and two short lists.** `field_equals`,
   `field_prefix_any`, `ordered_similarity`, and `deliverable_format` were 1.0
   in every cell that found the chain. There is no work product to retain, so
   there is nothing to get *partially* right.
5. **And the one genuinely hard sub-problem was an artifact.** Deciding
   whether `msg-000600` (June 12) was stale required ordering a Gmail date
   against a Slack `ts` that was simulation-relative seconds. That is not
   legal reasoning; it is epoch archaeology, and `db07e87` correctly removed
   it. Post-fix, this task's remaining difficulty is item 1: one search.

### The common mechanism

Both tasks ask for a **conclusion**, not a **work product**. When the answer
is a handful of scalars plus one short list, there is exactly one place a
model can lose points, so the score distribution is bimodal and clamped near
the top. The tasks that *did* separate models — `second-read-audit` at
0.2886, `visitor-log-audit` at 0.2793 — are the ones whose deliverable is a
71–75 row sourced ledger. Luna answered both headline questions perfectly and
scored under 0.30 because it did not retain the evidence. That is the design
that works.

---

## 6. Hardening recommendations

Constraint honoured throughout: **no recommendation below makes a grader
stricter.** Explicitly ruled out, because the evidence shows they would
measure the wrong thing:

- ~~Lowering agent timeouts~~ — DeepSeek's exact `operative-deadline` cell
  took ~30 of 60 minutes. Cutting the clock would convert a correct answer
  into a timeout and inflate apparent difficulty.
- ~~Raising exact-certification weight / removing F1 partial credit~~ — the
  0.4633 / 0.8180 / 1.0000 spread is already informative. All-or-nothing would
  collapse it to 0/1 and lose the diagnostic.
- ~~Adding more rows of the same kind~~ — the fee and billing screens prove
  the ceiling: Luna scored 1.0 on a 655-row certification with 173 MCP calls
  by writing a paginating client. Volume is a cost tax, not a difficulty
  mechanism.
- ~~Hiding evidence behind obscure tool paths, or capping calls~~ — the floors
  are already measured at 40–199 calls and every model clears them.
- ~~Removing the decoy pre-announcements to create gotchas~~ — see D1 below
  for the legitimate version of this.

Ranked by expected difficulty gain per unit of work.

**R1 — Give `operative-deadline` a work product. (highest gain, ~1 day)**
Add a `notice_audit` row for every communication in the matter that names any
noticed hearing date: the message ID, its surface, the date it cites, the
date operative *at the moment it was sent*, and a `current` / `stale` /
`correction` classification. This is the docket-contamination memo a docketing
clerk actually circulates, and the instruction already describes the rule
verbatim — "A message that reports the move, or that names the old date only
to deny it, is a correction, not a stale reference; a message citing a date
while that date was still operative is simply current." Today that reasoning
is applied to five items and rewarded as one F1 score. Applied to every
mention, it forces per-message chronological interpretation and makes
precision-1.0 under-claiming impossible, because omitting a row is as costly
as misclassifying it. Expected effect: the six 0.4633 cells cannot reach 0.5
by finding one Slack message, and the 0.8180/1.0000 cells must defend every
`current` call.

**R2 — Make one supersession legally contestable. (high gain, ~1 day)**
Every current supersession has an unambiguous instrument: a court notice or an
explicit clerk report. Add one move that is *reported* before it is
*effective* — a clerk's call relayed in Slack on day X, confirmed by written
notice on day X+3, with two messages sent in between that cite the old date.
Whether those two are stale depends on whether the reader treats the oral
report or the written notice as operative. Ship the answer with the rule
stated in the instruction ("the firm dockets from the first reliable report,
not the written confirmation") so it remains deterministic — but the agent
must now apply a rule to a genuinely contested interval rather than sort by
timestamp. This attacks exactly the step `kPYF6oU` got wrong for the wrong
reason, and now it would be wrong for the right reason.

**R3 — Give `standard-drift` a cross-surface reconciliation the diff cannot
answer. (high gain, ~1–2 days)**
Today `change_class` is a byte comparison, and 9/9 cells got the partition
exact. Replace the mechanical trigger with a documented-authority one: a
version is `substantive` when it changes an operative clause **and** the
playbook requires sign-off for that change, and the audit must record whether
the required sign-off exists — Managing Partner approval for a term
extension, a written waiver for residuals. Sign-offs live in Gmail and Slack;
some are given in a thread that never names the vendor and must be joined
through the matter or the redline's attachment ID. Add a `sign_off` field per
substantive row: `present` with its exact message ID, `absent`, or
`after_the_fact` with both dates. The population stays at 16 rows, so this
adds no volume — it converts a diff into a three-surface join with a legal
predicate. `version_audit.certified`, currently earned by nobody for an
accidental reason, would then be un-earned for a real one.

**R4 — Un-announce the traps, and pay for it with an explicit rule. (medium
gain, ~half day)**
Both instructions currently enumerate their own decoys ("Summit's covering
email lands the day AFTER its rider"; "a different case's hearing date is not
this hearing's"). Delete the enumerations and keep the *rules* that resolve
them ("a covering email is an email sent the same calendar day that names that
vendor or carries that file"; "cross-reference every noticed date against the
correction timeline"). The task stays fully determined and fully fair — the
agent can still derive every answer — but it must apply the rule to find the
edge cases rather than being handed a checklist. This is the cheapest change
in the list and it directly targets why 9/9 cells got the partitions exact.

**R5 — Fix the `process` dimension's tool-name coupling. (low gain, ~1 hour,
but it removes a false signal)**
`operative-deadline`'s `checked_stale_chat` criterion requires
`slack_search_public` and was missed by 9/9 cells, all of which used
`slack_search_public_and_private` — a superset. Every operative cell reads
`process = 0.875` for a reason that has nothing to do with process quality.
Accept either tool. This does not change reward, but it stops the diagnostic
from lying.

**R6 — Protect the paid evidence base. (no difficulty gain; prevents the next
loss, ~1 hour)**
Default `--jobs-dir` to a path outside the working tree, or refuse to launch a
paid matrix when `repository` resolves inside a `worktrees/` path without an
explicit `--jobs-dir`. The authoritative meter moved `56.005689513` →
`89.936100158` across this corpus — **`$33.93` of settled model spend over 47
cells** — and every trial artifact it produced was deleted with a worktree.
Independently:
persist a machine-readable per-cell summary (model, attempt, answer, process,
per-criterion values, MCP tool histogram, wall time, stop reason) into
`docs/runs/` at batch close, so the analysis in this document survives even if
`jobs/` does not.

**R7 — Re-baseline before drawing any further conclusion. (blocking,
cost only)**
Every cell in §1a–§1d predates `db07e87` (real Slack epochs) and `72f21cc`
(DST-aware oracle, instant-comparing verifier). The visitor screen moved
0.2793 → 0.3070 → **1.0000** across exactly those two commits with the same
model and the same task. **No score in this document may be carried forward as
difficulty evidence.** The five-task defeat target is not merely unproven; it
is unmeasured. The next paid batch should re-run `operative-deadline` and
`second-read-audit` at current revision *before* any hardening lands, to
establish how much of the observed spread was the timestamp artifact.

---

## Appendix: figures that could not be recovered

- Per-cell `started_at` / `finished_at` for every trial (wall times above are
  inferred from `docker ps` uptime snapshots).
- Per-cell MCP tool histograms for `standard-drift`, `operative-deadline`, and
  `second-read-audit` (only `codex.txt` byte sizes and narrative excerpts
  survive).
- Criterion detail for `second-read-audit__8mzC82r` (0.1219) and for the
  0.8944 `standard-drift` cells.
- Token accounting for all runs except `vanished-clause`.
- `gateway_provenance` records for all runs.
