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

## Remaining limitations

1. Seven tasks lack a final 3x3. No competence or defeat claim can be made for
   those cells.
2. The only completed task, fee dispute, has best-of-three answer 1.0 for all
   models and does not satisfy the defeat target.
3. OpenRouter's Responses result did not expose the selected upstream provider.
   Provenance certifies enforced order and fallback denial, not actual provider.
4. Harbor's default `harbor check` is model-based. It was not run for all eight
   tasks after the cap bound; static layout tests and an actual offline 8/8
   Harbor reference job pass.
5. Source hardening commit `dd6e11f` postdates the paid diagnostic matrix.
   A future final matrix must use a new run ID and rerun every cell under one
   fingerprint.

## Resume rule

Resume only after an explicit budget/cap change. Query the credits endpoint,
retain the `$1.50` reserve, use the then-current clean revision, and allow the
hardened runner to stop if its normalized full-batch forecast does not fit.
Never convert setup, provider, MCP, timeout, verifier, or meter failures into
low model scores.
