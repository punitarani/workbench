# Hartwell Harbor failure modes

This document records failures observed during the Harbor port and final paid
pilot. Invalid trials are operational evidence only; they are never model
scores.

## Resolved release blockers

| Failure | Effect | Repair and evidence |
|---|---|---|
| stale Clio materialization | money and billable truth predated current projectors | rebuilt all eight environments from the 9,427-event log; independent bundle queries rerun |
| exact-set cliffs | one set error zeroed otherwise useful answers | 90% Counter-F1 plus 10% exact certification for formerly exact set fields |
| reward aggregation mismatch | reference reward could depend on process | one Reward Kit run over answer/process; canonical `reward=answer` |
| deliverable symlink | verifier could follow `/tests/ground_truth.json` | `O_NOFOLLOW`, `fstat` regular-file check, and size bound |
| weak scalar typing | numeric timestamps and bool integers could certify | exact top-level and nested typed contracts before scoring |
| duplicate collapse | set conversion hid duplicate evidence | Counter-based one-to-one comparison and explicit extra penalties |
| deep JSON/trajectory crash | malformed input raised `RecursionError` or `TypeError` | bounded parsing and defensive process traversal return zero |
| fake unified-exec credit | comments, strings, and regex literals looked executable | JavaScript scrubber covers comments, strings, templates, regex statement contexts, and executable interpolation |
| setuid shell wrapper | `/bin/sh` dropped the environment effective UID | privilege-preserving `#!/bin/sh -p`; actual container reports EUID 10000 |
| arbitrary oracle arguments | agent could try to widen environment execution | fixed argument-free wrappers; extra arguments rejected |
| stale Harbor job reuse | old `result.json` files could be relabeled with current fingerprints | refuse existing report/job path, including broken symlinks, before launch |
| unsafe transport logs | exception text could contain request or secret data | fixed-category logging without exception text |
| score-contract acceptance | finite but out-of-range or `reward != answer` cells passed | enforce `[0,1]` and exact reward/answer equality |
| uncorrelated routing provenance | cumulative gateway records could not be tied to launches | persist sequence spans and per-trial fingerprints; label actual provider unknown |
| meter regression/post-cap gap | decreasing or over-cap post-launch readings could pass | reject regression; persist and stop on post-launch cap breach |
| in-flight forecast overrun | a long Harbor batch could spend far beyond its authorization before the next post-launch reading | poll authoritative credits every 30 seconds; terminate the paid process group at the authorized forecast or pre-reserve boundary |
| unstated UTC-to-Pacific conversion | correct iManage save timestamp was graded against an undisclosed firm-calendar conversion | instruction now names `America/Los_Angeles` and requires converting iManage UTC timestamps; regression test added |
| silent evidence-population shrink | canonical oracle bytes caught drift but did not state the professional workpaper's intended population | typed task metadata certifies primary record and nested evidence counts before staging |
| exception-only fee workpaper | the public path reviewed 254 activities but retained only 47 IDs on five silent days | return all 22 daily review rows with all activity and support identities; keep silent days as a reconciled exception view |

## Paid-run failures

### Remote compaction

Codex treats providers named `OpenAI` as supporting remote compaction. OpenRouter
supports Responses but not Codex's `/responses/compact` extension.

- Run A's remote-compaction v2 path produced `invalid_prompt`.
- Run B disabled v2, but the v1 path called `/v1/responses/compact` and received
  a 404.
- Repair: custom provider name `hartwell_gateway`, Responses wire API,
  WebSockets disabled, and local Codex compaction. Luna, GLM, and DeepSeek all
  subsequently completed valid long-context cells.

### Agent timeout

The fee task's 1,800-second Harbor timeout expired while GLM and DeepSeek were
still collecting evidence. Both trials had live containers and trajectories but
no deliverable. They were correctly invalid.

- Repair: Harbor agent-time multiplier 2.0.
- Targeted reruns completed at 0.8432 GLM and 0.6416 DeepSeek answer.
- Commit `dd6e11f` makes the multiplier part of the command and fingerprint.

### Budget forecast granularity

The original runner reused one dollar forecast for a three-cell smoke, six-cell
fee continuation, and nine-cell task batch. A six-cell launch therefore cost
more than its operator projection, although it stayed below the hard cap.

- Repair: maintain forecast in full-nine-cell units, normalize each observed
  launch by attempts per model, and scale it to the exact next launch size.
- The final settled meter is below the hard cap but below the required reserve,
  so no further paid launch is permitted.

### In-flight budget overrun

The 2026-08-11 second-read batch was admitted with a `$4.00` nine-cell
projection derived from the preceding standard and operative batches. Six
GLM/DeepSeek agents continued reconstructing the 75-row ledger for more than 35
minutes. A manual live meter check found nearly `$12` of in-flight usage. The
operator stopped the run; delayed settlement brought the batch to
`$12.940024093`.

- Three Luna results had already completed and are valid.
- Six `CancelledError` results have no verifier output and are invalid.
- Repair: `8e47e9c` runs Harbor in a dedicated process group, polls the
  authoritative meter every 30 seconds, and cancels the group when observed
  in-flight cost exceeds its launch authorization or consumes the reserve.
- Pre-launch projection and post-launch settlement checks still run. The live
  check is an additional guard against duration-driven cost drift and delayed
  discovery.

## Remaining limitations

1. The five-task best-of-three `<0.5` target is not established. Current
   standard and operative diagnostics are too easy; second read has only three
   valid Luna cells because GLM/DeepSeek were cancelled for budget protection.
2. Cancelled second-read cells and all still-unmeasured current evidence-ledger
   cells require a new authorization and exact current fingerprints.
3. OpenRouter's Responses result did not expose the selected upstream provider.
   Provenance certifies enforced order and fallback denial, not actual provider.
4. Harbor's default `harbor check` is model-based. It was not run for all eight
   tasks after the cap bound; static layout tests and an actual offline 8/8
   Harbor reference job pass.
5. The strict runner fingerprint includes git revision, task source,
   materialized environment, image, gateway, Harbor, Codex, provider order, and
   timeout multiplier. Diagnostic cells may guide design but cannot be silently
   relabeled as a final matrix after source or harness changes.

## Resume rule

Resume only after an explicit budget/cap change. Query the credits endpoint,
retain the `$1.50` reserve, use the then-current clean revision, and use at
least `$12.9401` as the long-ledger forecast until equivalent cheaper evidence
supports a lower value. Allow the hardened runner to stop an in-flight batch
when the live meter reaches its authorization.
Never convert setup, provider, MCP, timeout, verifier, or meter failures into
low model scores.
