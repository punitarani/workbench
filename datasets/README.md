# datasets

Harbor tasks, grouped into datasets — the eval/RL deliverable built on top
of recorded workplace days. Arrives with Phase 3 of the
[v1 design](../docs/superpowers/specs/2026-08-08-workbench-v1-design.md):
tasks are mined from simulated history, ground truth extracted from
offstage state, every task validated (solvable, discriminating,
deterministic, leak-free) before it lands here.

Task format: `datasets/<dataset>/tasks/<task>/` per Harbor's layout
(`task.toml`, `instruction.md`, `solution/solve.sh`, `tests/test.sh`).

## legal-nda

Both tasks mined from the same recorded legal day:

* **`legal-nda/tasks/vantage-triage/`** — reconstruct the clause-by-clause
  triage memo for the Vantage vendor NDA. The vendor-standard clauses
  (mutual, two-year cap, no non-solicit) exist only in Daniel's redline
  and email, never in the playbook, so a playbook-only agent provably
  scores less (0.48 vs 1.0).
* **`legal-nda/tasks/redline-provenance/`** — locate where today's
  redline edits actually live. The record contradicts the surface-obvious
  answer (the edits sit on a precedent file, not the inbound draft), so
  an assumption-only agent provably scores less (0.30 vs 1.0).

Workspaces are derived data and stay local; build them from a recorded
day with `uv run python datasets/legal-nda/build_task.py`.

## hartwell

Five tasks mined from the four-month Hartwell & Marsh history
(`uv run python datasets/hartwell/build_history.py --days all`, then
`uv run python datasets/hartwell/build_tasks.py` to materialize each
task's workspace from `out/hartwell/world.jsonl`). Workspaces are
seatless: Gmail projects the whole firm's mail org-wide, since the tasks
are matter-hygiene work that reads across seats. Every task is answerable
only by joining tools or version histories — never one document — and
each ships a naive single-source baseline that provably scores lower:

* **`hartwell/tasks/standard-drift/`** — show where vendor-NDA redline
  practice diverged from the written playbook, citing the divergent
  documents and versions (playbook revisions x NDA redline history x
  covering emails; playbook-only baseline 0.30 vs 1.0).
* **`hartwell/tasks/fee-dispute-reconstruction/`** — reconstruct the
  billing facts behind the May 8 Meridian invoice dispute: disputed
  minutes, entry count, timekeepers, challenger (Clio activities x the
  long matter note x the Gmail challenge; whole-April assumption
  baseline 0.35 vs 1.0).
* **`hartwell/tasks/vanished-clause/`** — find which Lumen license draft
  silently dropped the licensor indemnity, and who saved it under a
  formatting-cleanup comment (iManage v2/v3 content diff; impossible
  from any single version; email-trail baseline 0.45 vs 1.0).
* **`hartwell/tasks/client-departure-postmortem/`** — pin the Cascadia
  souring to dates: first internal warning (Slack), reaction decline,
  closure (Clio), disengagement letter (iManage/files), termination
  email (Gmail); email-thread baseline 0.25 vs 1.0.
* **`hartwell/tasks/operative-deadline/`** — establish the operative
  Arroyo hearing date; every email states a superseded date and the real
  one exists only in the final Slack correction (Gmail notice history x
  Slack; last-notice baseline 0.33 vs 1.0).
