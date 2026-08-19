# Postmortem: the two non-model, non-task failures

Only **M** may ship. **T** is fixed and re-run. Anything else — the
environment, the data, the tools — is unacceptable and owed an account.
This is that account. One environment defect and one class of harness
defect occurred; neither reached a shipped score, and both are recorded
here with what let them happen.

## E-1 — The staged bundle accumulated three worlds

**What.** `materialize` writes files and never removes them, and every
Ashgrove build since `epoch-r10` had been pointed at one directory. The
staged workspace held **161 files for a record containing 52 documents**:
workbooks and memos from two superseded worlds, describing engagements at
statuses the live record had long since left.

**Blast radius: none reached a score.** Every shipping task read
`state/`, which is projected from scratch on each build. Proven rather
than assumed: rebuilding with the workspace cleaned first returned
**twelve of thirteen oracles byte-identical**. The only oracle that moved
belonged to the one task that grades the files, and it had not yet been
measured.

**Why it survived.** Nothing had ever graded the workspace. A defect in
an unread surface is invisible by construction — there is no test that
fails, because nothing looks. It surfaced within an hour of the first
task that opened those files.

**Fix.** `build_tasks.build` now clears `workspace/` and `state/` before
materializing and prints the file count beside the document count, so the
two are visibly reconcilable on every build.

**Second, related defect found in the same pass.** `--refresh-truth`
defaulted to a fixed world path (`epoch/`) while the bundle shipped from
`epoch-r12` — a fresh answer key derived from a stale world. It never
fired only because the coherence gate refused the old world (20.7%
mis-booked). That is luck, not a check. It now reads the `SOURCE` file
the build records.

**Lesson.** Derived directories must be rebuilt wholesale, never
incrementally. Any check whose passing depends on another check happening
to fail is not a check.

## T-0 — The harness failures, and why they are not model failures

Not environment defects: the served surfaces pass reachability and the
vendor-parity suite. These are failures of the *agent harnesses*, and
each produced a `0.000` that looks exactly like a wrong answer.

| failure | signature | disposition |
|---|---|---|
| codex MCP bridge rejects gpt-5.6-sol | `tool exec invoked with incompatible payload`, 3,999 output tokens, nothing written | discarded; moved to hermes |
| opencode loops | agent repeats its opening line | harness abandoned |
| hermes subagent abandonment | 5-9 steps of a 90-step budget, 112-142 mentions of `subagent`, turn ends with children uncollected | **not discarded** — a completion *rate*, handled with k=9 |
| `AgentSetupTimeoutError` | 360s exceeded on `apt-get` + `nvm` + npm | budget raised to 600s x 2 |
| rate limiting | `clio.who_am_i` returns, then `RateLimitError`, three trials in a minute | **mine** — two sweeps on one account; serialised |

**The standing rule this produced.** A `0.000` has at least five causes —
wrong answer, harness incompatibility, rate limit, clock, and abandoned
delegation — and only the first is a capability claim. **Read the trial
log before recording the number.** `band.py` enforces the consequence: a
DNF is never averaged in as a zero, and a task needs two gradeable trials
per model before it reports a mean at all.

**Why the abandonment is not scored against the model.** It is a
property of how hermes orchestrates, not of whether gpt-5.6-sol can do
the work: the same model scores 0.997 on `approval-register` and 0.865 on
`opening-days-completion-claims` when it does not delegate. Scoring the
abandoned attempts as zeros would report "cannot do the task" for a model
that demonstrably does it.

## What was mine

Three of the failures above are my own tooling, not the system's: the
rate-limited trials, a four-hour queue deadlock caused by a monitor whose
own argv matched the process name it was watching, and a zsh
word-splitting bug (`set -- $spec` is a bash idiom) that failed nine
queued runs with `exit=2`. Each produced output that looked like a
finding. The measurement apparatus is part of the system being measured.
