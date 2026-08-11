# Hartwell Harbor suite checkpoint

Updated 2026-08-11.

## Current state

The suite is reproducible, securely staged, and reference-valid. The paid
hardness objective is still incomplete because the continuation budget cannot
cover another full matrix after a long-ledger cost overrun.

| Area | State | Evidence |
|---|---|---|
| Branch | active | `feat/resume-hartwell-harbor-suite` |
| Deterministic history | complete | 9,427 events; 77 cached pieces; 0 new content calls; 3,730,130 identical bytes |
| Fresh materialization | complete | all eight bundles rebuilt and oracle-certified from current projectors |
| Evidence generation | complete | typed build contracts certify all primary workpaper populations before staging |
| Public MCP surface | complete | Gmail 4, Slack 9, iManage 9, Clio 8 tools |
| Harbor schema | complete | eight schema-1.3 tasks on `workbench:dev` |
| Reward contract | complete | `reward=answer`; separate deterministic `answer` and diagnostic `process` |
| Reference solutions | complete | all eight `reward=answer=1`, `process=0` |
| Current Harbor oracle | complete | `hartwell-oracle-current-20260811-2`: 8/8, zero exceptions |
| Security boundary | complete | real container state/runtime denial, fixed wrappers, no-follow verifiers, malformed trajectory safety |
| Provider gateway | complete | pins/fallback denial, passthrough, secret-safe logs, provenance, freshness, lifecycle tests |
| In-flight budget guard | complete | 30-second authoritative polling and paid process-group cancellation |
| Paid standard diagnostic | complete | 9/9 valid; best answers 0.8944/0.9094/0.9094; too easy |
| Paid operative diagnostic | complete | 9/9 valid; best answers 0.8180/0.4633/1.0000; too easy for Luna/DeepSeek |
| Paid second-read diagnostic | partial | Luna 3/3 valid, best 0.2886; six GLM/DeepSeek cells cancelled and invalid |
| Five-task defeat target | not established | cancelled/unrun cells are not scores |

The final offline workspace gate completed with 772 passed, 13 skipped, and one
deliberately deselected test.

## Task ledger

Floors are measured metadata, not call limits. The evidence population is a
build-time contract.

| Task | Certified primary evidence | Floor | Reference | Naive |
|---|---|---:|---:|---:|
| fee dispute | 5 unsupported days / 47 activity IDs | 49 | 1.0000 | 0.6440 |
| client departure | 4 unanswered client emails plus cross-surface milestones | 10 | 1.0000 | 0.5340 |
| billing hygiene | 655 person-day rows / 4,233 billable IDs | 146 | 1.0000 | 0.2226 |
| second read | 75 first-response rows / 12 DM lanes | 54 | 1.0000 | 0.5130 |
| visitor log | 71 first-return custody rows | 54 | 1.0000 | 0.5356 |
| operative deadline | 3 supersessions / 5 stale references | 40 | 1.0000 | 0.1753 |
| standard drift | 16 post-v1 NDA rows / 4 covering emails | 48 | 1.0000 | 0.3738 |
| vanished clause | 57 revision rows / 53 covering communications | 199 | 1.0000 | 0.2152 |

## Continuation spend boundary

- baseline: `64.274128970`;
- additional authorization: `$25.00`;
- final settled usage: `84.197153415`;
- continuation spend: `$19.923024445`;
- remaining before cap: `$5.076975555`;
- launchable after reserve: `$3.576975555`.

The observed long-ledger worst case is `$12.940024093`, so the remaining amount
cannot safely authorize another nine-cell batch. No further paid work should be
launched under this ledger.

## Resume condition

Resume only after a new explicit authorization. Record the settled meter as the
new baseline, retain `$1.50`, use a forecast of at least `$12.9401` for a long
ledger until better identical-protocol evidence exists, and start a fresh run
ID from a clean current fingerprint. Never reuse or score cancelled, timeout,
setup, provider, MCP, verifier, stale-source, or meter-failure cells.
