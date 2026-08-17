# Why each criterion missed — the E/T/M ledger

Every score below 1.0 is a defect until proved otherwise. **E** is an
environment defect (the fact is not served, or the record contradicts
itself with no stated rule), **T** is a task defect (ambiguous instruction,
wrong oracle, wrong grader, unfair tolerance), and **M** is a model failure
— reachable, unambiguous, oracle independently confirmed, and the agent got
it wrong anyway. Only **M** may ship.

World: `epoch-r12`, 11 workdays, 6,150 events, `validates=True`, coherence
clean, 0.1% mis-booked time. Model: Opus 5 through codex, one trial each.

## commitment-register — 0.783 over three trials — all misses M

```
answer                            0.783    0.770 - 0.808  (k=3)
answer.commitments.f1             0.961    0.949 - 0.985
answer.row_facts                  0.918    0.892 - 0.969
answer.commitments_total          0.000    all three trials
answer.messages_with_commitment   0.000    all three trials
```

Three trials, a spread of 0.038, and the same two counts zeroed in every
one: the over-matching is systematic, not a lucky draw. The classification
below is from the first trial, read row by row.

Recall was perfect. **The agent found every one of the 388 rows and added
42 of its own**, so this is precision, and every one of the 42 was checked
against the message it came from:

**34 contain none of the seven stated forms.** The agent read deadlines out
of prose the instruction rules out in as many words — *"Exactly these seven
forms… Nothing else counts, however deadline-like it sounds."*

| what the message actually said | why it is not a commitment here |
|---|---|
| "Harbor Light and Ashfield wrap **end of week**" | `EOW` is not among the seven; `end of day` is |
| "Fairmount queues **early next week**" | not a listed form |
| "**Wednesday 14:30** works for the GL sync" | a meeting time, not `by Wednesday` |

**8 are rows the oracle already has, at the right date, with a second
wrongly-dated copy attached.** `msg-000122` says `end of day`, which the
instruction resolves to the sent date, 2026-01-08; the agent also filed it
under 2026-04-15 — the tax deadline named elsewhere in the same message.

**Verdict M.** The oracle passes its independent derivation from the world
log, every value it names is served, the rule is stated twice and
emphatically, and the model applied its own judgement about what a
commitment *is* instead. That is the failure this environment exists to
measure, and it is worth naming precisely: **rule-literalism under semantic
temptation**. The model's competence at reading intent is what hurt it.

## tracker-reconciliation — 1.000

No miss to classify. Built specifically for correlated error — one sheet,
three bridging decisions, each moving all 139 effort rows together — and
solved perfectly in 26 shell commands. Recorded in `DIFFICULTY.md` as the
measurement that closed the correlated-error hypothesis.

## work-product-review — 1.000

No miss to classify. Worth noting what changed: on the previous world this
task's key collapsed 52 documents to 49 and capped a perfect answer at
0.94. Re-keyed on iManage's served document number, the ceiling is gone and
the model reaches it.

## engagement-time-allocation — 1.000, client-responsiveness-sla — 1.000

No misses to classify. 188 rows over 1,260 time entries and 43 threads
respectively, both perfect. These are the tasks `DIFFICULTY.md` records as
proof that width does not create difficulty.

## The suite on r12, Opus 5, one trial each

| task | rows | answer |
|---|---|---|
| **commitment-register** | 388 | **0.770** |
| tracker-reconciliation | 139 + 10 | 1.000 |
| work-product-review | 52 | 1.000 |
| engagement-time-allocation | 188 | 1.000 |
| client-responsiveness-sla | 43 | 1.000 |

One task in band; four at ceiling. The one that moved is the one whose
rule a competent reader is tempted to override.

## Retired

**engagement-status-integrity.** Its answer on r12 is empty — nothing moved
backwards anywhere, and twelve of fourteen engagements never changed status
at all. A task with no rows grades nothing: every agent that reports
nothing is exactly right. Retired rather than repaired, because the world
became coherent, which is the outcome that was wanted.

Its history is the reason this ledger exists. It once scored 0.067, and
establishing that as **E** — clio served no matter history at all — took a
rollout, a tool fix and a careful re-read. The task was sound the whole
time.
