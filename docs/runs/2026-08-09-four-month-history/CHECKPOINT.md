# Hartwell Harbor suite checkpoint

Updated 2026-08-10. This replaces the pre-Harbor checkpoint.

## Current state

The suite implementation is complete and reproducible. The paid evaluation is
not complete because the recorded `$25.00` OpenRouter cap is now binding.

| Area | State | Evidence |
|---|---|---|
| Branch | complete | `feat/resume-hartwell-harbor-suite` |
| Deterministic history | complete | 9,427 events; 77 cached content pieces; zero new content calls; 3,730,130 byte-identical bytes |
| Fresh materialization | complete | all eight task environments rebuilt from the current projectors |
| Public MCP surface | complete | Gmail 4, Slack 9, iManage 9, Clio 8 tools |
| Task truth and shape | complete | eight independent bundle/oracle suites pass |
| Harbor schema | complete | all eight tasks use schema 1.3 and `workbench:dev` |
| Reward contract | complete | `reward = answer`; `answer` and `process` retained separately |
| Reference solutions | complete | all eight return `reward=1`, `answer=1`, `process=0` |
| Security boundary | complete | actual container probes cover database/runtime denial, restricted oracle execution, and verifier-readable deliverables |
| Provider gateway | complete | alias restoration, fixed provider order, fallback denial, streaming/error passthrough, safe logging, cleanup, freshness, and metering tested |
| Offline Harbor run | complete | 8/8 references completed with no exception and full answer reward |
| Final Python/static gates | complete | 682 passed, 13 skipped, 1 deselected; Ruff check/format and diff check pass |
| Paid final matrix | blocked by cap | fee dispute has a valid 3x3; seven task matrices were not launched |
| Defeat target | unmeasured | fee dispute does not defeat the three models; the other seven tasks have no valid final cells |

## Task ledger

Floors are metadata, not hard call limits. Naive scores use the repaired
Reward Kit answer dimension.

| Task | Current invariant | Reference calls | Reference | Naive |
|---|---|---:|---:|---:|
| fee-dispute-reconstruction | 7 disputed entries; 5 unsupported days; 47 audit entries; 2,887 minutes; 2,057,692 cents | 49 | 1.0000 | 0.6440 |
| client-departure-postmortem | repaired email, termination, document, and Slack IDs | 10 | 1.0000 | 0.5340 |
| billing-hygiene-audit | 3 person-days; 18 entries; 876 minutes; 687,600 cents; phantom note 176 | 146 | 1.0000 | 0.2226 |
| second-read-audit | 75 requests; 12 DM lanes; 66 same-day responses; 3 unanswered | 54 | 1.0000 | 0.5130 |
| visitor-log-audit | 71 requests; 59 same-day; 10 next-working-day; 2 unresolved; 12 breaches | 54 | 1.0000 | 0.5356 |
| operative-deadline | five-reference supersession reasoning | 40 | 1.0000 | 0.1753 |
| standard-drift | silent versions `LEGAL!11`, `LEGAL!23`, `LEGAL!27`, `LEGAL!36.3` | 48 | 1.0000 | 0.3738 |
| vanished-clause | 36 documents; 32 multi-version; 31 clean multi-version documents | 199 | 1.0000 | 0.2152 |

## Valid paid cells

All nine fee-dispute cells used the same task materialization, image
`sha256:aff89613a1e90b38f58782f86ff383293ca5c55f38f06eb6a1f1cb2e0be21052`,
Codex 0.147.0, Harbor 0.18.0, gateway v2, and pinned provider routes. The
valid task/gateway source revision was `8aaa868`.

| Model | Attempt 1 answer/process | Attempt 2 | Attempt 3 | Best answer |
|---|---:|---:|---:|---:|
| `openai/gpt-5.6-luna` | 1.0000 / 1.0000 | 1.0000 / 0.8333 | 0.6920 / 0.8333 | 1.0000 |
| `z-ai/glm-5.2` | 0.8432 / 1.0000 | 1.0000 / 0.7750 | 0.8432 / 0.9083 | 1.0000 |
| `deepseek/deepseek-v4-flash-0731` | 0.6416 / 0.8625 | 1.0000 / 0.7500 | 0.9800 / 0.7500 | 1.0000 |

The fee task therefore does not satisfy the `<0.5` best-of-three target for
any model.

## Spend boundary

The authoritative credits meter moved from the recorded `32.2139` baseline to
`56.005689513`, or `$23.791789513` of project spend. Only `$1.208210487`
remains before the cap. With the required `$1.50` reserve, launchable budget is
negative, so no further paid batch is authorized.

## Resume condition

Do not reuse the fee cells as final cells after source hardening commit
`dd6e11f`: the final fingerprint now includes the 2x agent-time multiplier and
launch-size-aware cost projection. When the user changes the project cap or
provides a new evaluation budget, start a new run ID from the then-current clean
revision and rerun all eight 3x3 matrices. Never count the three remote
compaction failures or two 1,800-second timeouts as model scores.
