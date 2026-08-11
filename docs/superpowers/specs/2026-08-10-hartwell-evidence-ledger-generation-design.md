# Hartwell evidence-ledger task generation

## Objective

Generate at least five practical legal audits whose primary deliverable is the
complete evidence-to-conclusion work product a lawyer would retain, not a small
answer set distilled from a much larger review. The three pinned models must
each score below 0.5 on three valid attempts. Difficulty must come from a
professionally justified rule and a complete synthetic record, never from a
hidden call cliff, arbitrary decoy, brittle parser, or weakened grader.

## Evaluation evidence

The first current-revision quiet-drop batch produced eight valid cells and one
3,600-second DeepSeek timeout. Valid agents used 181–552 MCP calls. Every valid
agent found the Lumen indemnity drop; five of eight also certified the five
unreviewed revisions exactly. Luna scored 1.0/0.844/0.835, GLM scored 1.0 on all
three attempts, and DeepSeek scored 1.0/0.8688 with the timeout excluded.
Every non-exact score lost points only on the communication reconciliation set.

The current output therefore discards the hard part of the work. Agents inspect
57 post-v1 revisions and dozens of same-day communications but return only five
unreviewed IDs. The improved tasks will grade the complete evidence ledger that
supports the conclusion.

Later current-era diagnostics confirmed the design boundary. `standard-drift`
with a 16-row ledger remained easy (best-of-three 0.8944/0.9094/0.9094); its
consistent remaining miss was an unstated UTC-to-Pacific date conversion, now
fixed as a fairness defect. `operative-deadline` produced a meaningful repeated
0.4633 partial reconstruction, but Luna reached 0.8180 and DeepSeek reached 1.0
by continuing the evidence sweep. Compact conclusions and small schedules are
therefore diagnostic tasks, not candidates for the five-task hardness claim.

The 75-row `second-read-audit` produced three valid Luna answers at
0.2886/0.2886/0.1219. The 0.2886 answers got every headline finding right but
matched only one ledger row. This is the desired separation between conclusion
quality and retained-workpaper completeness. GLM/DeepSeek were still
reconciling the full workpaper when the operator cancelled them to protect the
explicit spend reserve; those six cells are invalid and provide no score.

## Generation pipeline

`build_history.py` remains the deterministic source-world generator and keeps
storyline/coherence invariants. `build_tasks.py` will materialize each bundle,
run the task's restricted stdout oracle against the fresh databases, and compare
its canonical JSON bytes with a committed offstage oracle artifact. An explicit
refresh mode updates those artifacts after an intentional storyline or rule
change; the default build fails on drift. Harbor staging occurs only after the
oracle check, so stale projected databases or stale expected answers cannot be
evaluated.

Each `task.toml` also carries a typed `[metadata.evidence]` contract naming the
primary retained workpaper, its exact row count, optional nested source-ID
count, and the product surfaces joined to derive it. The default build validates
that contract against the freshly emitted oracle before byte certification and
staging. This makes scope shrinkage visible even when an intentionally refreshed
oracle would otherwise bless a smaller task.

Each hardened task owns a deterministic builder inside its self-contained
solution. The same builder emits the reference deliverable and supplies the
expected evidence ledger used by tests. Dataset tests independently rederive
the high-level counts and parity invariants from the fresh database rather than
trusting the committed artifact alone.

## Five evidence-ledger contracts

1. **Quiet-drop carrier audit.** Retain the dropped-protection finding and add
   one revision record for every post-v1 revision of every multi-version
   document. Each record contains the version ID, document number/path, save
   date, coverage status, exact same-day Gmail message IDs, and exact same-day
   public Slack timestamps. Current invariant: 57 revisions, 52 covered, five
   unreviewed, and 53 covering communications.
2. **Meridian fee-support audit.** Retain the challenged diligence entries and
   add one daily record for every date in the post-cutoff April review window.
   Each record accounts for every Meridian activity, minutes, billed cents, and
   every qualifying same-day Gmail or Slack identity. Current invariant: 22
   daily rows, 254 activities, 28 supporting communications, and five silent
   days in the separately graded exception view.
3. **Second-read supervision review.** Return all 75 requests, not only the three
   misses. Each row records the request, participants, first qualifying response
   surface/ID/timestamp, and same-day, next-working-day, or unanswered outcome.
4. **Visitor-log custody review.** Return all 71 requests with the first
   qualifying return surface/ID/timestamp and same-day, next-working-day, or
   unresolved outcome. The existing 12-breach summary remains the management
   view of that ledger.
5. **Billing hygiene certification.** Retain the three anomalous person-days and
   18 entries, but add the exact other-person Clio activities/notes that
   corroborate each affected matter/day. This turns an anomaly flag into an
   e-billing review file that another lawyer can reproduce.

Vendor-NDA playbook drift remains a useful compact diagnostic, but its complete
16-row ledger was easy for all three models and is not one of the five hardness
candidates. Client departure remains a candidate for the same retained-workpaper
pattern if paid evidence shows one of the five above is still too easy;
operative deadline is a sound reasoning diagnostic but proved too compact.

## Verifier contract

Answer criteria use strict, size-bounded, no-follow JSON loading and reject
non-finite values, wrong scalar types, missing/extra keys, malformed nested
records, and excessive depth. Structured collections use typed canonical tuples
and `Counter` semantics so ordering is neutral while duplicate or invented
evidence is penalized. Every collection keeps the suite's 90% normalized F1 / 10%
exact-certification split. Aggregate counts and partitions are graded separately
and must reconcile with the records.

The primary ledger carries most answer weight because it is the retained legal
work product. A submission that reports only the headline conclusion scores
below 0.5, but a well-typed near miss retains proportional credit. `reward`
continues to equal `answer`; `process` remains a separate diagnostic.

Synthetic tests cover the reference, honest near misses, missing rows, wrong
citations, shotgun rows, duplicates at every nesting level, reordered sets,
wrong types, extra keys, NaN/infinities, deep JSON, oversized files, symlinks,
missing/malformed trajectories, and genuine versus mention-only unified-exec
tool use. Harbor references must score `reward=answer=1.0` with no exception.

## Evaluation and analysis loop

Every task change invalidates all prior cells for that task. Run a new clean
revision and staged environment through three attempts for each pinned model.
Setup, provider, timeout, MCP, and verifier failures are invalid and rerun only
after their cause is corrected. Use criterion details and trajectories to
distinguish rule misunderstanding, incomplete enumeration, timestamp/join error,
tool-surface friction, timeout, and grader exploit. Use `harbor analyze` on a
representative exact and non-exact trajectory when the evaluator can be routed
through the same secret-safe gateway; its reward-hacking and task-specification
findings supplement, but do not replace, deterministic adversarial tests.

Paid work uses settled-meter checkpoints, explicit incremental caps, and the
$1.50 reserve. The matrix runner polls credits during the launch as well as
before and after it, and terminates the paid process group if observed cost
exceeds the launch authorization or reaches the reserve. Offline history
generation, truth derivation, reference runs, security probes, and verifier
adversarial tests precede each paid rerun.
