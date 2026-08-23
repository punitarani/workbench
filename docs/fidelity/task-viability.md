# Which staged tasks the corpus can actually support

> **STATE AS OF 2026-08-22, late.** This file is a running record, ~1,900
> lines, written in the order things were found — including the several
> places where a later measurement overturns an earlier one. Read those
> corrections as the point rather than as noise: every one of them is a
> number that looked settled. Where an earlier section and a later one
> disagree, **the later one is the measurement.**
>
> **A second screen now applies to every row below, and it changes
> verdicts.** A reader who reports every candidate has recall 1.0 by
> construction, so its row F1 is fixed by rows ÷ candidates alone. Across
> twelve tasks in two datasets that predicts the measured dump floor at
> r = 0.892. A task whose answer is a large share of its own candidate pool
> cannot punish reporting all of it, however good its rule is.
>
>     task                      forms/premise      rows/cands   floor
>     live-commitment-register  BUILT and probed        0.07     0.444
>     prebill-narrative-screen  file/filed, 47% off     0.097     —
>     no-op-revision-register   1 form grades 0         0.083     0.363
>     off-sense-register        88 hits, 109 decoys     0.077     0.474
>     unanswered-question-reg   sound on its premise    0.333     0.556  ⚠
>     deadline-week-promise     3 of 7 forms grade ~0   0.476     —      ⚠
>     double-booked-week        RETIRED — 5 clashes
>     court-clock-computation   RETIRED — 4 messages in 67 days
>     one-sentence-two-dates    RETIRED — 0 real two-date sentences
>
> The two flagged rows each have a measured menu of tightenings in their own
> `CANDIDATE-RATIO.md`; the best reach 0.10–0.13 and 0.169 respectively.
> `deadline-week-promise`'s 0.476 is against the *honest* pool — declaring
> the wider one measures 0.223, which is the direction of error to watch,
> because a generous candidate count makes a task look better while being
> no harder to dump.
>
> **What clears its floor.** Only `live-commitment-register` has been
> measured against a model at all, and the result splits: against the top of
> the dump bracket [0.171, 0.444], opus is **+0.085** and glm is **−0.012**.
> The design moved a frontier model off 1.000 *and* clear of dumping, which
> this dataset had not managed before. glm's 0.432 is what dumping scores.
>
> **Three engine defects are pending and v7 carries all three** (see
> `pending-engine-fixes/`): the calendar creates every occurrence at day
> zero, so 89% of invitations are never visible and `rsvp_needsaction` fails
> its band; every reviewer is permanently assigned one document, so 30 of
> 325 documents have a second reader and **no new pairing has appeared in 26
> days**; and one RSVP verb. Only the second touches a task — exactly one
> task reads `imanage.db`, `no-op-revision-register`, so letting v7 finish
> costs that task and nothing else.
>
> **v6 is dead** (day 67 of 130) and carries a cross-surface fiction about a
> bug in its own engine, so it builds and probes tasks but does not grade
> them. **v7 is at day 71 of 180** on the corrected engine. Transferable
> rules live in `task-design-laws.md`; floors are gated in
> `datasets/merrick/baselines.py`, which refuses a dump floor ≥ 0.8 and warns
> at ≥ 0.6 — 10 of ashgrove's 17 tasks would refuse and the other 7 warn.

---

Measured on the recording in progress at **day 13 of 130** — 595 message
bodies, 2,325 time entries, 55 documents. Rates, not totals, are what
carry to the full window; each row below extrapolates linearly and says
so.

Every one of these five tasks was authored *before* the world existed,
from a picture of how a law firm writes. Three of the five premises turn
out not to match what the firm actually writes. That is the entire reason
the `«MEASURE»` placeholders exist, and it is cheaper to find here than
in a rollout where a starved rule reads as a model failure.

## Verdicts

| task | mechanism | measured | verdict |
|---|---|---|---|
| `off-sense-register` | word admitted in a non-register sense | `confirm` 200 msgs, `file` 51 | **ship** — narrow the word list to these two |
| `deadline-week-promise-clock` | promise → due date → followed up? | 4 of 7 forms live; followed-up 39% | **ship** — 4-form table, not 7 |
| `prebill-narrative-screen` | defective time-entry narratives | 48 defects in 2,325 (2.1%) | **ship bounded** — see below |
| `one-sentence-two-dates` | two forms, one sentence, different dates | ~0 real instances | **retire** |
| `court-clock-computation` | interval form + calendar date | 0 and 0 | **retire** |

## Why the two retire rather than widen

`court-clock-computation` needs `within N days` (0 occurrences) *and* a
`<Month> <day>` date (0). Both halves absent.

`one-sentence-two-dates` looked alive at 18 messages until the text was
read. Fourteen were **compound spellings of one deadline** — `by tomorrow
EOD`, `EOD Friday` — where two form words name a single date. The rest
were multi-item lists sharing a due date: *"Earnout terms — call EOD
tomorrow"* and *"Northmoor diligence — due EOD tomorrow"* in one message
is two items on one date, not two dates.

A count matched the premise; reading the matched rows refuted it. **The
detector agreed with me and the data did not.**

Widening either rule — admitting `two weeks`, or counting compound
spellings as two dates — would swap a rule the firm does not write for a
rule nobody stated, and the register would then measure the author's
vocabulary rather than the model.

## Why `prebill-narrative-screen` must be bounded

2.1% of entries are defective: 35 vague openers, 8 notes of three words
or fewer, 5 billable blocks of four hours or more, 0 orphans. At the full
window that is roughly **480 defects in 23,250 entries**.

Unbounded, that is a coverage task, and coverage difficulty is bimodal —
a model either sweeps the corpus or samples it, and the score lands near
1 or near 0 rather than in the band. Bound it to one matter for one
month, ~200 entries with a handful of defects, and the difficulty moves
into the *rule*: which of these notes actually violates the stated
standard. Rule difficulty survives bounding; coverage difficulty does not.

## What the corpus carries in volume

Replacements should be drawn from here rather than from imagination.
Counts are 13 workdays, extrapolated in brackets.

| signal | events | at 130 days |
|---|---|---|
| time entries, median 11-word note, 59% billable | 2,325 | ~23,000 |
| `EOD`/`COB` deadlines | 104 msgs | ~1,000 |
| calendar events / responses | 750 / 138 | ~7,500 / ~1,400 |
| `confirm` in a message body | 200 | ~2,000 |
| meetings with transcripts | 75 | ~750 |
| document revisions / creates | 104 / 55 | ~1,000 / ~550 |
| tickets created / updated | 31 / 48 | ~310 / ~480 |

Two replacements are needed. The volumes above admit several shapes the
current five do not touch — a calendar with 1,400 responses supports a
scheduling-commitment task; 750 meeting transcripts support extracting
what was agreed in a room against what was later written down.

## A fidelity gap found while sizing a replacement, and left open

**Meeting transcripts reach no served surface.** The world records them —
93 meetings and 474 spoken turns by day 15, so roughly 800 meetings and
4,000 turns over the full window — and the calendar projection handles only
scheduled/updated/response payloads. Every word said in every meeting is
generated by the same models that write the mail, and no agent can read any
of it.

A task was designed on those transcripts and built to the point of a
working projection, three new tables and two read tools before the
constraint that kills it showed up in the suite:

> `test_no_invented_tools`: *"An agent trained against an invented tool
> learns a call that fails in the real product."*

Google's Calendar API has nine tools and none of them serve a transcript.
Parity is worth more than the task — it is what makes an agent's knowledge
of the real product transfer — so the change was reverted whole.

**The fix, when it is made, goes to iManage.** A law firm files meeting
minutes in its document system, and that surface already has
`download_document`, `search`, `get_document_profile` and
`get_document_versions`. Transcripts become documents; no tool is invented.

It is left open deliberately rather than half-landed. Projecting ~800 new
documents changes the artifact-mix floors, the document/path parity count
and the coherence graph, all of which are being watched against a live
recording, and none of that should move while the world is still being
written.

**What this costs:** the richest untapped prose in the world stays
unreadable, and one replacement task had to be designed elsewhere.

## A third retirement, and the check that would have caught it in one line

`double-booked-week` was built, verified against an independent second
derivation, and retired within the hour. The measurement that justified it
was this:

> 54 pairs genuinely overlap, **240 touch exactly**. A reader who treats
> touching as clashing scores 16% precision. Four traps per signal.

Every number there is correct. The task is still dead, because the number I
did not compute is the one that mattered:

| clashes | count |
|---|---|
| on 2026-01-05, day one | **47** |
| later, inside 2026 | **2** — one pair, counted for two attendees |
| dated 2080–2081 | 5 |
| between two *identically titled* events | 21 |

Day one carries 87% of the signal. The first reading was a seeding burst;
it is not one. **No event is genuinely scheduled on day zero** — 45 of them
carry a wall-clock time of day (`31500` = 08:45) in a field holding
seconds-from-epoch, so they collapse onto the epoch's date and each overlaps
every other. 96% of every conflict in the world involves one of them, and
outside that pile-up the firm produced **one** genuine diary clash in
seventeen working days — about eight over the whole
window. Including day one grades a startup artifact; excluding it leaves a
register with eight rows that needs the entire epoch as its window, which
destroys the bounding the task depends on.

**The lesson is new and it is one line of code.** This is not the
coverage-versus-rule distinction and not a vocabulary miss. It is that *a
rate computed over a window can be dominated by a boundary artifact*, and a
total will never show it. Group by date before believing a count:

```python
collections.Counter(day_of(row) for row in signal)
```

Applied immediately afterwards to the replacement task, the same check found
the mirror-image artifact at the *other* end of the record: questions asked
on the last recorded day are 4-for-4 "unanswered" because the world stopped
before anyone could reply. That one shapes the rule instead of killing the
task — the register needs a fixed response window and must close several
working days before the record does.

## Two defects in the recorded world, neither fatal

Found while sizing the above, both left alone because the engine is frozen
until the recording completes and restarting has already cost this project
nine resets to day zero.

**Sixty-eight of 784 calendar starts (8.7%) are not seconds-from-epoch** —
47 carry a time of day and 21 carry an absolute Unix timestamp, fifty-four
years past the epoch. The earlier note here said eleven, which counted only
what fell outside a 200-day horizon and missed the larger and more damaging
class entirely. No windowed task can see them — every window is at most 130 days
and these sit billions of seconds beyond the cutoff — but a law firm whose
diary holds a meeting in 2081 is a fidelity defect, and an agent browsing
the calendar would find them.

**Twenty-one clashes are between two events with identical titles**, mostly
`Meet-and-Confer — Motion to Compel` against itself. Personas are creating
duplicate calendar entries for one meeting rather than finding the existing
one. Realistic in small doses; twenty-one is generation, not behaviour.

## The suite measures fewer skills than it has tasks

An audit lens raised this and it survives checking. Classifying the five
survivors by what a model must actually *do*:

| task | primary demand | secondary |
|---|---|---|
| `off-sense-register` | admit only a closed set of literal strings in prose | completeness over a corpus |
| `no-op-revision-register` | admit only a closed set of literal phrases in prose | precision on a minority class |
| `deadline-week-promise-clock` | admit only a closed set of date forms | a forward join |
| `prebill-narrative-screen` | admit only a closed word screen | rounding arithmetic |
| `unanswered-question-register` | walk a thread graph | working-day arithmetic |

**Four of five turn on the same skill**: resisting the urge to generalise a
closed literal set to what the sentence obviously means. That skill is worth
measuring — it is the lever that reliably lands a task in band here, and it
is a real failure mode. But a suite of five tasks that grades it four times
carries roughly the signal of a suite of two.

This is not an argument for weakening the levers that work. It is an
argument about what the *next* task should target, and there is a natural
opportunity: `deadline-week-promise-clock` is under review for retirement
because its forward join decides 0–3 rows. If it retires, its replacement
should be chosen for the gap rather than for the mechanism that is easiest
to land.

**Uncovered, in rough order of value:**

*Cross-surface reconciliation.* Two records of the same fact that disagree,
where the rule states which one governs. Nothing in the suite currently
requires holding two surfaces against each other; the closest is a forward
join within one surface. The world supports it — timekeeping, documents and
correspondence all describe the same matters.

*Numeric aggregation with a stated convention.* Not rounding as a trap, but
a total a reader must assemble from many rows under a rule about what is
included. `prebill` touches this and is dominated by its word screen.

*Negative space.* Every register here asks what is present. Asking what is
**absent** — a required step nobody took, a person nobody assigned — is a
different search, and one this record can answer deterministically.

Recording it here rather than acting now, because the choice depends on
whether `deadline-week` survives its measurement at the full corpus, and
that measurement does not exist yet.

## A confirmed audit finding that does not reproduce

`deadline-week-promise-clock` was rated high-severity dead by one lens and
**confirmed by its adversarial verifier**: *"3 of 7 forms are dead, the
dominant form needs no date arithmetic, and the forward join decides 0–3
rows."*

Measured independently on the same record:

| graded week | rows | followed up | not |
|---|---|---|---|
| 2026-W02 | 12 | 4 | 8 |
| 2026-W03 | 38 | 20 | 18 |
| 2026-W04 | 26 | 12 | 14 |
| 2026-W05 | 11 | 3 | 8 |

Eleven to thirty-eight rows per graded week and a follow-up column that
splits roughly evenly. The join is not degenerate and the register is not
starved. **The task ships.**

The other two claims hold and both are recorded in the solver: three of the
seven date forms never occur and the table must be narrowed to four, and
`EOD`/`COB` is 62% of hits and resolves to the send date, so only 38% of
rows need any date arithmetic — real, but a minority of the work in a task
whose name promises a clock.

**The point worth keeping is about the audit, not the task.** The verifiers
were told to refute by default and they killed ten of forty-three findings
on exactly that standard. A confirmation is still a claim. Applying the same
scepticism in the other direction cost one measurement and saved a viable
task from retirement — and, since it is the fifth, saved authoring a
replacement for it.

## The dry-run ceiling was the expected result, and the real question is elsewhere

Six frontier-class attempts across two briefs all returned F1 = 1.000. Read
alone that looks like two tasks with no difficulty in them. It is not what it
looks like.

The band is a **mean over three tiers** and a budget on the weak pair: with
the frontier at 1.000, the other two must sum to ≤ 1.40. Frontier 1.000 is
the precondition, not the failure — a task is defective when the frontier
*misses*, because then nobody can do it. The three tasks that landed in band
on the comparison world scored 0.576, 0.761 and 0.774 on that mean.

What the in-band task actually measured is recorded and worth restating: the
weak model **read 1,574 of 1,585 messages and still produced 48 of 110
rows.** It was not failing to find the text. It caught 23 of 82 occurrences
of the admitted word — applying the stated rule to prose it had already read.
That is rule difficulty, it is a rate, and it survives bounding. Its lever
was an off-sense share of **79%**.

So the useful question the dry run raises is not "are these too easy" but
**"does each task have an off-sense lever at all?"**

| task | lever | off-sense share |
|---|---|---|
| `off-sense-register` | the admitted word means something else | 66%, measured |
| `no-op-revision-register` | admitted phrases against near-misses the record actually writes | present — `no edits were made`, `no edit was made`, `no edit made` all occur and are all excluded |
| `deadline-week-promise-clock` | date forms, four live of seven | partial: 62% of hits are one form needing no arithmetic |
| `prebill-narrative-screen` | a family over time-entry notes | **not found** — best probe 53% and misread upward |
| `unanswered-question-register` | a plain request that carries no `?` | 29% one way, 24% the other — measured below |

**Correcting the line above.** This table first said the task had no lever
at all, on the reasoning that a literal `?` is unambiguous so there is
nothing to be wrong about. That was looking for the lever in one direction
only. Measured on 258 mail messages with a To recipient:

| | count | |
|---|---|---|
| plainly asking the addressee for something | 91 | |
| ...carrying a `?` | 65 | admitted |
| ...carrying none | **26 (29%)** | **excluded, and plainly an ask** |
| carrying a `?` | 85 | |
| ...not plainly asking anything | **20 (24%)** | **admitted, and not an ask** |

The excluded ones read exactly like the rows a partner would want chased:

> *"I need you (or HR) to pull it and send it to me today"*
> *"Adaora — can you pull together a one-pager tonight covering:"*

Both are unmistakable requests to a named addressee. Neither carries a
question mark. A reader working from meaning takes them; the stated rule does
not. That is the same lever as every other task in this suite, arriving from
the other side: not *the admitted form means something else*, but *the
register's own idea appears constantly without the admitted form*.

So the honest ranking is that this lever is **weaker, not absent** — roughly
41% of the decision points are cases where meaning and spelling disagree,
against 66% for `confirm` and 79% on the in-band comparison task. Weaker in
the same units, which is a measurement rather than a verdict.

**Measure it in the real sweep rather than rebuilding it now.** If the weak
pair sums well above 1.40 the repair is to strengthen this lever rather than
invent one — the corpus supports it, and `can/could you` without a `?` on
that clause runs at 68% on its own.

## Re-measured at day 61: three of four rates moved, and one crossed its gate

Every viability number in this document was measured between days 12 and 35.
At day 61 the corpus is roughly four times larger. Re-run with the same
classifiers, so the comparison is like for like:

| rate | when first measured | at day 61 |
|---|---|---|
| off-sense share of `confirm` | 66% (day 30) | **56%** |
| no-op revisions, share of versions | 18% (day 16) | **9%** |
| EOD share of mail date-forms | 62% (day 30) | 56% |
| questions unanswered in 3 working days | 35% (day 22) | 39% |
| date forms with zero occurrences | 3 of 7 | **2 of 7** |

**`off-sense-register` no longer clears its own 60% gate.** An audit claimed
at day 30 that no family in this corpus cleared it; I refuted that with a
66% measurement and the refutation was correct *then*. The claim is becoming
true as the corpus grows. That is not the auditor being right by luck — it
is a rate measured on a fifth of a corpus, quoted as a property of the
corpus.

**`no-op-revision-register`'s minority class halved.** 18% was comfortably
inside the 15–40% band where both precision and recall bite; 9% is heading
toward the needle-hunt end, where scores go bimodal. The audit said "one in
ten on the record" and was closer than I was.

**A retired task's premise partly revived.** `by <Month> <day>` had zero
occurrences and now has six. `court-clock-computation` still stays retired —
it needs an interval form *and* a calendar date in one body, and `within N
days` remains at zero — but the reason has narrowed from "neither half
exists" to "one half exists".

### Is there a better family at day 61? No — and the number moves with the classifier

The corpus has grown enough that families dead at day 16 now clear the row
floor: `resolve` 170 messages, `agree` 296, `complete` 79. Screened over all
2,795 messages, with the minority-form share the task's own script reports
and an off-sense share from the same sentence-scoped classifier used above:

| family | minority form | off-sense | verdict |
|---|---|---|---|
| `confirm` | 39.8% | 60% | best available, sitting on the gate |
| `file` | 33.0% | 58% | |
| `review` | **6.6%** | 66% | highest off-sense, fails the minority-form floor |
| `agree` | 26.7% | 49% | |
| `resolve` | 23.5% | 52% | |
| `complete` | 15.2% | 58% | |

`review` is the only family clearing 60% off-sense and it fails the other
hygiene check — its minority spelling is 6.6% of hits, well under the 20%
floor, so the two admitted forms would be one form wearing two hats. Nothing
beats `confirm`, which now sits exactly on its gate rather than comfortably
above it.

**The number moves with the classifier, and that matters more than the
ranking.** The same corpus and the same question gave 56% and 60% for
`confirm`, four points apart, differing only in whether the off-sense
patterns included `should`, `before` and `un-` prefixes. Neither reading is
wrong; the boundary between "asking someone to confirm" and "confirming" is
genuinely fuzzy at the edges, which is exactly why the task's own screen
says the off-sense test "always blocks until a human reads the sample".

So: do not settle this with a regex. A four-point classifier swing straddles
the gate, and the decision it feeds — whether this task ships as written —
deserves a hand-classified sample of the finished corpus, not a third
automated estimate.

### What this means for the fills

Do not fill any `«MEASURE»` from a number in this document. Every one of
them is a reading of a smaller corpus. The three re-measured downward are
the ones that decide whether two tasks are viable at all, and both need to
be re-run on the finished record before their windows are chosen.

The direction is not random. Both rates that fell are **minority-class
shares**, and a minority class dilutes as the majority accumulates: more
messages carrying `confirm` in its ordinary sense, more revisions that
really did change something. A rate that is a *proportion of a growing
population* should be expected to drift; a rate that is a *count per working
day* should not. Worth checking which kind a number is before quoting it.

## Re-measured across a *different recording*, and that is not the same thing

Everything above re-measures one world as it grows — day 13, then day 61 —
and closes with the right warning about proportions of a growing
population diluting. This section is the first re-measurement against a
**differently recorded world**, and the effect is larger, differently
caused, and not predicted by the drift rule above.

Measured at day 28 of the corrected-engine recording against the same
window of the previous one, identical extraction, on meeting transcripts:

| conjunct | old world | new world | ratio |
|---|---|---|---|
| owner phrase (`I'll`, `I will`) | 55% of turns | 47% | 0.86x |
| matter named | 47% | 56% | **1.21x** |
| weekday named | 30% | **14%** | **0.47x** |
| all three together | 37 turns | **10** | 0.27x |

**This is not dilution.** Dilution moves every proportion the same way; here
one conjunct halved while another rose. The firm changed how it writes
deadlines — 243 turns now carry `end of week` / `EOD` / `COB` / `tomorrow`
against 83 naming a weekday — and a task whose rule admitted weekdays only
would have shipped with six rows, under the twelve-row floor, and **not one
supersession**. Its entire mechanism would have been absent, and it would
have scored a frontier model 1.000 for taking the first answer, because
there was never a second one. Admitting both forms gives 31 rows with 32%
superseded on the same window.

**Why a whole conjunct can move between recordings.** The engine changed.
Personas now observe meetings being scheduled, held and answered — three
payload kinds that previously reached nobody — so they have something to
refer back to and less need to restate a date. A rule measured on a world
recorded by a different engine is a rule measured on a different firm, and
no amount of corpus growth in the old world would have revealed it.

So the document's closing warning needs a second clause. Do not fill a
`«MEASURE»` from a number here **and** do not carry a verdict across a
re-record: the verdicts above are engine-specific, not merely
corpus-size-specific.

### What else moved, measured the same way

| premise | old | new | verdict |
|---|---|---|---|
| `off-sense-register`: `agree`/`agreed` | 598 rows / 5,894 msgs | 68 / 904 at day 28, both forms firing | **holds** |
| `prebill-narrative-screen`: rounding disagreement | 76.6% of matter rows | **83.3%** | **stronger** |
| `deadline-week-promise-clock`: `end of month` | 0 messages | 0 | dead in both |
| `deadline-week-promise-clock`: `by date` | 3 of 2,717 messages | 0 | **dead — and was effectively dead before** |
| malformed calendar starts | 532 of 1,255 (42.4%) | **7 of 539 (1.3%)** | fixed |
| `slack.dm_share` | 0.000 | **0.250** | fixed |
| `slack.threaded_reply_share` | 0.0003 | **0.433** | fixed |

Two of those need acting on rather than noting.

`by date` was **effectively absent in the old world too** — five occurrences
across three of 2,717 messages, which is none at all in any window a task
can use — and the screen printed it without comment because it flagged only
an exact zero. It became visible only when the new recording made it a true
zero, so the guard fired on the second world for a row already dead in the
first. `measure_promise_week.py` now reports EFFECTIVELY ABSENT under ten
messages. That is the same calibration mistake the fidelity band gate made
(refusing `observed == 0` let a metric through at 0.000315): **a check that
fires only on exactly nothing is calibrated to the one case somebody
already thought of.**

`double-booked-week` was retired because the calendar was 42.4% malformed
and the served diary was half-size. That cause is fixed, so its recorded
reason is now false and anyone rechecking it would revive the task. The
real reason holds on both worlds and was never written down: **this firm
does not double-book** — 2 overlapping pairs in 180 days of the old world,
1 in 30 days of the new, across 21 and 27 diaries. Its `task.toml` now says
so. A stale retirement note is worse than none: it is a measured-sounding
claim pointing at a fixed cause.

### How this was measured before the recording finished

Seventeen hours before the world was due, on a run still in progress:

```
./.venv/bin/python scripts/export_world_log.py --out <scratch>   # run.db -> world.jsonl
# then tools.project_all(read_events(world.jsonl), <scratch>/state)
WORKBENCH_STATE=<scratch>/state uv run python datasets/merrick/measure_*.py
```

The export is safe against a live recording — SQLite is in WAL mode, so it
reads a committed snapshot while the writer continues. Do this at day ~25
of every re-record. Every finding in this section came from it, and each
one would otherwise have surfaced during the turnaround, when the cost of
a starved rule is a rollout that reads as a model failure.

### Resolved: `deadline-week-promise-clock` ships with five rows

Two of its seven form-table rows are dead on the new world (`end of month`
and `by date`, both zero), and the build now refuses a dead category
outright rather than shipping a `form_counts` key an agent scores by
writing 0. The open question was whether what remains is enough of a task.

It is. Ranked by rows *and* by how many rules a week exercises, on 33
recorded days:

    2026-02-02   60 messages read, ~26 rows, 5 of 7 forms
    2026-01-12   64 read, ~26 rows, 4 forms
    2026-01-19   55 read, ~21 rows, 4 forms

Twenty-six rows over sixty messages, exercising five distinct rules, clears
the twelve-row floor with room and is a lighter read than the ~213-message
window the in-band precedent settled on. Ship the five live rows; do not
retire.

Two things to carry into the fill. The week above is the best of the
*first 33 days* — re-rank on the finished record, because later weeks are
unmeasured and the ranking is what picks the window. And every one of the
seven excluded wordings the brief warns about (`end of the week`,
`end-of-day`, `by Saturday`, `by <Mon>. <day>`) occurs **zero** times here,
so the brief must say each is moot on this corpus rather than implying a
reader will meet one — a warning about a thing that never happens is a
sentence spent teaching nothing.

### `unanswered-question-register`: the recorded fix does not work

Its dump floor was measured at 0.556 — an answer that reports every
candidate question as unanswered scores over half marks — and the recorded
plan was to lengthen the silence window so fewer questions qualify.

Measured, the curve is nearly flat:

| grace | old world unanswered | new world unanswered |
|---|---|---|
| 1 working day | 49.3% | 57.3% |
| 3 working days | 40.9% | **53.0%** |
| 5 working days | 37.0% | 51.3% |
| 8 working days | 34.7% | **50.4%** |

Going from three working days to eight moves the new world's dump
precision by **2.6 points**. The reason is structural: most unanswered
questions are never answered *at all*, not answered late, so extending the
grace only catches the few stragglers. And the new world is worse than the
old — 53% against 41% — so the floor rises rather than falls.

**A dump scores well here because the base rate is high**, and no window
length changes a base rate. The lever has to be something a dump gets
*wrong*, not something that shrinks the admitted set:

* the row fields already carry `asked_of` and the thread — a dump can fill
  those from the same scan, so they add nothing;
* narrowing the population (questions asked of exactly one addressee, or
  in threads over some length) lowers the base rate directly, and is worth
  measuring before the window is chosen;
* the honest alternative is to accept the floor and report it beside every
  score, which `baselines.py` already does. A task whose floor is 0.69 is
  not useless — it is a task whose numbers mean less than they look, and
  saying so is cheaper than a redesign that does not move it.

These figures come from an approximate extraction — a body containing `?`,
sent to a named addressee, answered by any of them in the same thread —
not from the task's own solver, which is stricter. Treat the *shape* as
robust and the levels as indicative; re-run with the real solver on the
finished record before choosing.

#### What does move it: narrow the population, measured

Following the note above rather than leaving it as advice. Each narrowing
applied to the same corpus, on the new world:

| narrowing | candidates | unanswered | dump F1 |
|---|---|---|---|
| all questions (current rule) | 117 | 53.0% | **0.693** |
| asked of exactly one person | 115 | 53.9% | 0.701 |
| not the thread's opening message | 30 | 33.3% | 0.500 |
| **in a thread of 3+ messages** | 63 | **25.4%** | **0.405** |
| one addressee AND thread of 3+ | 61 | 26.2% | 0.416 |
| body *ends* with the question mark | **0** | — | dead narrowing |

**Thread length is the lever.** It drops the dump floor by 0.288, and it is
also the sharper question: a question in a thread that *kept going*, which
the person asked never answered, is a dropped ball. A question in a
one-message thread is a note nobody needed to answer. The register becomes
"what did the firm let slide while it was still talking", which is what a
practice administrator actually chases.

Two costs, both real. It halves the candidates, so the window must be
longer to clear the twelve-row floor — 16 unanswered in 39 recorded days
is about 0.4/day, so a thirty-day window sits *on* the floor and a longer
one carries more reading than the ~213-message precedent. And "asked of
exactly one person" does nothing at all (0.701 against 0.693), which is
worth knowing before somebody spends a build on the intuitive narrowing
rather than the measured one.

`body ends with the question mark` matches nothing in this corpus. It is
recorded so the next person does not re-derive it: people ask a question
and then keep writing.

#### The email fix may kill this task rather than rescue it

The dump floor above is high because 53% of questions go unanswered, and
that rate is substantially engine failure: 48.5% of question-bearing
threads lost a reply to the recipient refusal. The obvious inference is
that fixing replies fixes the task. Measured on a four-day pilot of the
fixed engine, against the *same four days* of the unfixed one:

| same 4 days | emails | questions | answered within 3 working days | unanswered |
|---|---|---|---|---|
| old engine | 16 | 8 | 6 | **25%** |
| fixed engine | 47 | 17 | 17 | **0%** |

Every question answered. A register of unanswered questions over that world
has **no rows**.

**Read both numbers as early-window, not as the world's rate.** The unfixed
world reads 25% unanswered at four days and 53% at forty-three: the rate
climbs as a backlog accumulates, so a four-day figure is not comparable to
a forty-three-day one, and the pilot's 0% will not stay 0%. Seventeen
questions is also a very small sample.

What this does establish is the *direction*, and it is the opposite of the
comfortable assumption: the fix does not move this task's base rate toward
a healthy middle, it moves it toward zero. The task may be unviable on both
worlds for opposite reasons — too many artefact rows on the unfixed one,
too few real ones on the fixed one.

So do not treat "re-record with the email fix" as the repair for this task.
Measure the unanswered rate on the finished record at the window actually
chosen, and if it lands near zero, the task retires on the same evidence
that retired the other three — the corpus does not carry the thing it
grades.

## The transcript corpus, measured on 56 recorded days of v6

Measured mid-recording, by backing up the live `run.db`, exporting a world
log from the copy and materializing it — the recording was untouched. Every
number below is **partial and must be re-measured on the finished record**;
they are here for the shape they establish, not the values.

    sqlite3 backup out/merrick/epoch-v6/run.db -> <scratch>/probe/run.db
    uv run python scripts/export_world_log.py --out <scratch>/probe
    environment.materialize(<scratch>/probe/world.jsonl, <scratch>/probe/bundle)
    WORKBENCH_STATE=<scratch>/probe/bundle/state uv run python \
        datasets/merrick/measure_transcripts.py

247 meetings, 1,257 turns, 91,177 words — over the 60,000-word ceiling, so
`live-commitment-register` needs a window, not the record. A 30-day window
is 93 meetings and 34,026 words, comfortably inside it.

**The material is there.** 510 turns carry a first-person commitment, 178
of those also name a deadline, and 86 also name a matter that resolves.
That yields 47 (speaker, matter) pairs, 36 of them named in two or more
separate meetings, and **19 change their deadline by the last mention —
53%**. A reader who takes the first answer and stops is wrong about half
the register, and cannot know it without crossing meetings.

### Three findings that constrain the design

**Nobody says a matter number.** Zero turns in 56 days contain a display
number in any form. Matters are named by the handle in their description
(`the Ardmore closing`), so the brief's requirement to report the display
number is a *resolution* step the agent performs against clio — not
something it can copy out of a transcript.

**20 of 34 matters cannot be named out loud at all**, so no commitment
about them can ever be keyed. Two causes, both now reported by the screen:
descriptions that are common nouns (`administration`, `pro bono`,
`regulatory inquiry`), and descriptions the engine minted mid-run as status
sentences rather than names. `Sandhurst` names four matters at once after
two were minted, so a turn saying it names none of them uniquely.

**The day field has a 64% guessing floor.** Live deadlines are `eod` 30,
`tomorrow` 11, `thursday` 4, `end of week` 2. Answering `eod` everywhere
scores 64% of the day field with no reading — invisible in the
supersession rate, which is why the screen now prints it. This is less
damaging than it looks: the floor is only reachable by a reader who has
already found the rows, and finding a row requires reading the turn that
makes it. But it does cap what keying on `day` buys, and the earlier
estimate in `tests/criteria.py` (row_facts 0.584 → 0.168) was computed
against a day field assumed to be informative. **Re-derive it.**

### Two defects in the emergent matters, for the next engine pass

Neither is fixable in v6 — the engine fingerprint is frozen for the run.

* **Minted descriptions are status sentences, not names.** `Priyanka
  Sandhurst Clearance Confirmation Pending`, `Sandhurst Platform
  Acquisition — Whitfield/Odell Good Standing Tracking`. The second
  duplicates the seeded `00010-NorthmoorCapital`. Seeded descriptions are
  `Client - handle plus noun phrase`; minted ones are not, and nothing
  checks the shape.
* **A firm matter whose responsible attorney is the client's CEO.**
  `00033-Ravndal` has `responsible_person = per-priyanka-deshmukh`, who is
  `affiliation=external`. One matter in 34, and `check_coherence` cannot
  see it: the reference resolves, so there is nothing dangling. The check
  verifies *existence* and not *class*. A firm-side role held by an
  external person is the check that was missing. (The 23 matters whose
  `originating_person` is external are the seeded convention — the client
  contact who brought the instruction — not this defect.)

### The chat decline is the world settling, not decaying

Chat fell from 24.7 messages a day over the first fourteen recorded days to
14.4 over the last fourteen, which looked like degradation and is not. It
is a step at day 21, not a slope, and `calendar.response` steps with it
(−53.5%): both drain the same pending list, and what changed at day 21 is
that the seeded invitation backlog cleared. Everyone still wakes the same
147 times a day and nobody is idle.

The per-person split that looked alarming — five partners falling to near
zero in chat while others rose — is role differentiation, and it reverses
completely in the room: the five quietest in chat are the **loudest
speakers in meetings**, with Dov Reinhardt first throughout. Transcript
turns per ten-day band are flat (200/128/156/154/143/152). The corpus a
transcript task reads is not affected by any of this.

## `live-commitment-register` is not gradeable as specified, and the reason generalises

Measured on the 56-day partial bundle, before any `«MEASURE»` value was
filled. **Do not fill them.** The brief's three-part rule — a person taking
work on, a matter named in the turn, a deadline — describes something the
corpus does not write.

    turns with a first-person commitment AND a deadline     178
      ...that also name a matter (the task would grade)      63   35%
      ...that do not (the task would discard)               115   65%

Two thirds of the firm's actual commitments are discarded for a reason that
has nothing to do with whether a commitment was made — the speaker simply
did not happen to say a matter name in the same breath. What gets discarded
is not marginal material; it is the clearest commitments in the record:

> *"I'll have the statement of facts to Bennett by tomorrow night."*
> *"I'll have it back to Ulrich by Wednesday."*
> *"I'll have all four out by thursday."*

And what is *kept* is worse. In the 63 turns that qualify, the matter name
sits a median of 96 characters from the commitment, and in **33% of them
more than 120 characters away** — a different sentence of a 71-word turn.
One qualifying turn attaches a commitment to Sable Ridge in a clause where
the speaker says she has *nothing* on it, and takes its deadline from
`ahead of tomorrow's call`, which is not the deadline of anything she
promised.

**The rule and the concept have come apart.** The brief says "a commitment
about a matter"; the oracle can only implement "a turn containing a
commitment token, a date token and a matter token". On short turns those
agree. On 71-word turns they do not, and the disagreement is not noise — it
is systematic in both directions. An agent reading correctly would produce
a different register than the oracle, and the task would score its
correctness as failure. That is the oracle-defect class that fakes a model
failure, reached from a new direction: not a wrong answer key, but a
**rule that cannot be expressed over the unit the corpus is written in.**

The general form, worth carrying to the next task: *a conjunctive rule is
only safe when its conjuncts are scoped to the same unit.* Speaker and
deadline are properties of the turn. "Which matter this is about" is a
property of a clause, and no amount of care in the brief makes a regex over
a turn into a reader of clauses.

### The reframe that does work, measured

Key the register on **(speaker, meeting series)** — "in each standing
meeting, what did each person last say they would have done, and by when" —
and the ungradeable conjunct disappears. Speaker is recorded, series is
recorded, deadline is stated. Nothing needs resolving against clio.

    window        mtgs   words   rows  superseded  first-answer wrong
    days  0-29      93  34,026     24          43        12/24   50%
    days 10-39      89  31,952     25          30        11/25   44%
    days 20-49      92  32,875     26          36         9/26   35%
    days 20-64     140  50,113     32          64        13/32   41%

Against the matter-keyed version's 14–18 rows at 6–21% wrong, this is
roughly 25 rows at 35–50% wrong, inside the word ceiling, with every field
directly observable.

**One measured objection, and it is real.** In the days 20–49 window the
live deadline is `eod` for 18 of 26 rows — 69%. (First measured as 77%,
before `EOD tomorrow` was recognised as one deadline rather than two; see
the correction below.) So supersession here is
mostly *"something → eod"*, which has a perverse consequence: a reader who
never opens a transcript and answers `eod` everywhere scores **higher on
the day field than a careful reader who takes each person's first
statement**. The lazy answer and the correct answer correlate, and the
diligent-but-naive answer is the one that loses. Before this ships, either
the deadline vocabulary has to be less concentrated on the finished record,
or the graded field has to be something `eod`-guessing cannot reach —
`superseded_count` is the candidate, since it is unavailable to any reader
who did not cross meetings.

The concentration is itself a world-quality finding: `by EOD` is a stock
phrase the personas reach for, not a distribution a real firm would
produce. Re-measure it on the finished record before deciding.

### Grade the resolved due date, not the token — measured

Two corrections and one design change, all from the same pass.

**`EOD tomorrow` is one deadline, and a naive rule reads it as today.**
40% of commitment-bearing turns name two deadline forms, and the dominant
pair is `eod`+`tomorrow` in 47 of 178 turns — the phrase *"I'll confirm the
date by EOD tomorrow"*. A first-match-wins rule over an ordered form table
returns `eod` and is wrong by a day in **26% of all graded turns**. Any
solver here has to match the compound before either part.

**Simulation seconds are not Unix seconds.** `meetings.started` is an
offset from the run's epoch. Read as a Unix timestamp it yields 1970 dates
that parse cleanly, sort correctly, and put 30% of the firm's meetings on a
Saturday or Sunday — a fidelity defect that does not exist. Convert with
`epoch + timedelta(seconds=started)` and every meeting is on a weekday at
08:45–09:30, which is what the recorded day labels say (58 recorded days,
all Mon–Fri). The engine's own `CalendarScheduleSpec` exists to stop this
mistake in the other direction; the analysis side had no such guard.

**The design change.** Grade the **resolved due date**, not the token.
`EOD` said on 3 February and `EOD` said on 20 February are the same word
and different obligations, so the register's answer cannot be guessed from
the vocabulary:

    window      rows   token: guess/wrong    date: guess/wrong
    days  0-29    24        54%  /  54%          17%  /  67%
    days 10-39    25        64%  /  40%          20%  /  64%
    days 20-49    26        69%  /  35%          23%  /  69%
    days 20-64    32        47%  /  44%          16%  /  72%
    days  0-79    38        47%  /  50%          16%  /  66%

The guessing floor falls from ~47–69% to ~16–23%, and the first-answer
reader's error rate roughly doubles, to 62–72%. The reason it doubles is
the useful part: **a person who says `EOD` in two different meetings has
changed their deadline without changing their words.** Token grading cannot
see that; date grading makes it the common case. This is the "second
statement inside a unit the reader has already resolved" mechanism — the
only one this project has measured moving a frontier model — applied to
about two thirds of the rows rather than a third.

It also buys a second thing: the date is only computable from the meeting
the last statement was made in, so a reader who has the right owner and the
right series but the wrong meeting still gets the date wrong. `meeting_id`
stops being decoration and becomes load-bearing.

**What the brief then owes the reader,** because each is a real convention
the corpus exercises: that `EOD tomorrow` is one deadline; that a weekday
names its *next* occurrence, including when the meeting falls on that same
weekday (3 turns) or later in the week than the day named (26 turns); that
`tomorrow` said on a Friday means Monday (3 turns); and that `end of week`
means that week's Friday. Every one of these is stated because it occurs,
not for completeness.

**Recommended shape when v6 lands:** window days 20–64 (45 days, 140
meetings, 50,113 words — inside the 60,000 ceiling), 32 rows, 72% of them
wrong for a first-answer reader, 16% guessing floor. Re-measure all of it;
these numbers are from 56 partial days.

## The first real probe, and what it measured that reasoning did not

Built `live-commitment-register` against the 56-day partial bundle and ran
it for real: `scripts/rollout.py --model opus-5 --k 3`, through the pinned
gateway, against the staged environment. Three findings.

### The window's own baselines, from `build_tasks`

    no_work_at_all                          0.000
    reported_every_candidate_counts_wrong   0.171
    empty_register                          0.273
    reported_every_candidate                0.444   <- ignores supersession

Against this dataset's five killed designs, whose fifteen measured
wrong-branch payoffs had a **median of 0.90**, and against the
matter-keyed version of this same task, whose wrong branch scored 0.687.
Ignoring supersession entirely now costs more than half the reward.

### 1800 seconds is not enough

All three trials hit the agent wall with no deliverable written, and the
harness retried all three into the same wall. The agent was not stuck. It
had dumped the window's transcripts to a scratch file and was paging
candidate turns twenty at a time — the reading the task exists to require.
`task.toml` had asked, in a `«MEASURE»`, for someone to time a real read
before trusting 1800; nobody had, and the answer is that it is too short
for 140 meetings and 51,672 words. Now 3600.

A timeout that cuts off honest work does not measure difficulty. It
measures the clock, and downstream it is indistinguishable from a model
that cannot do the task — which is the harness failure this dataset has
already mistaken for a score once.

### A count in a brief is a specification

The filled brief listed the admitted deadline forms *with a count for
each*: "end of day — 66 turns; tomorrow — 42; a named weekday — 28; the
compound `EOD tomorrow` — 15". The agent read that as a target to
reproduce. It wrote

    target eod66 tom42 wd28 eodt15 total151

into its own scratch file and spent turns trying counting modes against
it — 223 matches under one, 270 under another — because raw match counts
over overlapping patterns are **not a partition** and cannot be reproduced
by anyone, including the person who measured them. The counts were true;
they were also unreachable, and they sent a careful reader hunting a
consistency that does not exist.

Measure the forms to choose them. Publish only the forms. The skeleton now
says so where the value gets filled, which is the only place anyone will
read it.

**Refined against a brief that gets this right.** `off-sense-register`
publishes counts freely — "*agreement* alone appears in thirty-five of this
window's messages... not one of them makes a row" — and no agent has ever
chased them. The difference is what the count is *about*. A count of the
**answer's own composition** is a specification: it describes the thing
being graded, so a careful reader treats it as a constraint to satisfy and
loses if it cannot be reproduced. A count of **excluded** material is
illustration: reproducing it earns nothing, so nobody tries, and it does
the job it was written for — telling the reader how expensive the obvious
mistake is. Publish the second freely; never publish the first unless it is
an exact, reproducible partition.

**The general shape** is the session's through-line arriving from a new
direction: not a stale claim this time but a *true* one, put where it reads
as a requirement. Anything a brief states, an agent will try to satisfy.

## What the realism bands say about v6, sorted into real and inherited

The build reports "34 pass, 36 fail, 21 absent of 91 (most were written for
an accounting firm)". That parenthesis has been doing a lot of work, so the
failures are sorted here once. Measured on the finished 67-day v6 record.

**Inherited, and not defects.** `Clients on the book 10 against 120–200`,
`Engagements 37 against 250–500`, `Top-10 client share 1.0 against
0.35–0.55`, `Gini by client 0.41`. This firm has ten clients and
thirty-odd matters *by construction* — the workplace spec says so. A band
calibrated on a 200-client accounting practice cannot pass here and should
not; it needs re-aiming at the firm it now describes, which is a separate
job from this one.

**Real, and worth fixing in the engine.** Each of these is a statement
about behaviour rather than about scale:

    RSVP still needsAction     0.666  against ≤ 0.1
    RSVP accepted              0.329  against 0.6–0.8
    RSVP tentative / declined  0.000 / 0.005  against 0.05–0.15 each
    Cancelled events           0.000  against 0.03–0.08
    Emails per day, firm-wide  9.96   against 60–120
    Thread depth, median       1.0    against 1.5–3
    Announced-then-attached    0.774  against ≥ 0.9

Two thirds of invitations are still never answered even after the
invitation fix, and of those answered nobody ever declines or answers
tentatively — the firm has one RSVP verb. Nobody ever cancels a meeting.
Mail is six times too quiet and its threads do not develop: a median depth
of 1 means the typical email is never replied to at all, which is the same
defect the reply fix addressed from the sending end and evidently did not
finish. The `announced-then-attached 0.774` line in that table is **withdrawn**;
see the correction below.

**The one that changes how tasks should be written.** Cross-surface volume
correlation is **0.12 per matter and −0.12 per person**, against a band of
≥ 0.45. Per person it is *anti*-correlated: the people busiest on one
surface are the quietest on another.

That is not noise, it is the role differentiation measured directly
earlier — the five partners who fall to near zero in chat are the loudest
speakers in the room, and Dov Reinhardt is first in meetings throughout
while ending near the bottom in chat. A real firm's senior people are busy
*everywhere*; these personas specialise into a surface. So "the busiest
person on this matter" is a question with a different answer per surface,
and any task that asks it without naming the surface is ungradeable for
the same reason the matter column was.

None of this is fixable in a recording already running. It is written down
so the next engine pass has a list rather than an impression.

### Why the mail is six times too quiet: it is the firm that is silent

`Emails per day, firm-wide` reads 9.96 against a band of 60–120, and the
shortfall is not spread evenly. Split by affiliation on the 67-day v6
record:

    the firm's 21 staff       276 emails   4.1/day   0.19 per person per day
    the 10 client contacts    431 emails   6.3/day   0.63 per person per day

**The client contacts out-write the firm's own lawyers by 3.3× per head,
and produce 61% of all its mail.** Seven of the eight busiest senders in
the record are external. A lawyer at this firm sends one email per five
working days.

That is backwards for a law firm's corpus, and it is a different defect
from the reply-routing one fixed earlier — that was mail *attempted and
refused*, this is mail never attempted. The external personas exist to
inject work and reach for mail because it is the only surface they have;
the internal personas choose among chat, documents, tickets, time entries
and meetings, and mail loses. Fixing the routing raised the yield on
attempts; nothing raised the attempt rate.

Worth stating plainly because it bounds what mail-based tasks can be:
a task keyed on the firm's own correspondence is drawing on four emails a
day, not sixty. The transcript corpus is unaffected — meetings are 9/day
throughout and 30% of everything anyone says.

## Opus 5 on the finished task, and the defect the score exposed

Second probe, on the finished 67-day v6 record, window days 42–88 (Monday
16 February – Friday 3 April), 143 standing meetings, 726 turns, 53,960
words, 33 rows. `opus-5`, k=3, agent timeout 3600s. Wrong-branch floors
from the build: `reported_every_candidate` 0.449, `empty_register` 0.273,
`no_work_at_all` 0.000.

**The first completed trial:**

    meetings_read       143 / 143   exact
    turns_read          726 / 726   exact
    distinct_owners      13 / 18
    superseded_count     57 / 77
    rows                 22 / 33     row_f1 0.364
    pairs, ignoring the date  21 / 33

`meetings_read` and `turns_read` are exact, so the reading happened — this
is not a coverage failure. The register it built from that reading is where
it loses, and **the date is most of it**: of the 21 (owner, meeting) pairs
it found, only 10 carry the right date. That is the mechanism working as
designed.

**But part of the loss is mine, and the probe is how it was found.** The
brief states the deadline forms as a closed set and gives only an *example*
for the owner form. So the two sides of the same rule were written
asymmetrically, and the agent generalised — correctly, by the brief's own
words. Dov Reinhardt's Partner-matter-review row is the clean case: the
oracle takes his 16 February *"i'll have a firm answer by eod"*, and the
agent takes a 30 March turn reading *"i'm calling their counsel"*. That
does say he will do something. The brief admits it and the oracle does not.

The agent is broader than the oracle on some turns and stricter on others —
22 rows against 33, but only one of its rows spurious — which is the
signature of a boundary the brief never pinned down. A score built on that
measures agreement with a regex, not comprehension.

**The fix, and it is the same shape as the deadline table.** Name the
admitted owner forms as a closed set, with the concept beside it so a
careful reader converges on the same turns rather than guessing:

> The speaker is taking it on themselves, in the first person, about a
> **future** act — written `I'll` or `I will`. A report of what is already
> under way (*"I'm calling their counsel now"*) names no future act and
> makes no row. Work handed to somebody else is an instruction and makes a
> row for nobody.

That keeps the difficulty where the design put it — resolving a relative
deadline against the right meeting, and noticing the later mention that
moved a date without changing a word — and takes it out of guessing which
verbs the author admitted.

**Read the score accordingly.** 0.364 is in band, and it is an *upper
bound on the task defect's cost* rather than a clean measurement of the
model. Re-probe after the brief is symmetric.

## The email fix, seen on the engine that carries it

v7 records on the corrected engine; v6 did not. Over the first 7 recorded
days of each:

    email.message      6.4/d -> 10.1/d   x1.58
    rejections        12.1/d ->  8.0/d   x0.66
    chat.message      24.7/d -> 18.3/d   x0.74
    work.time.logged 169.7/d -> 170.3/d  x1.00

**The ratio is not an intervention effect**, and this file has been wrong
that way before. Two recordings from the same seed are the same world only
until the first action resolves differently; after that they are different
draws, and chat moving 0.74 in the same window — on a surface the email fix
cannot touch — is the reminder. Seven days is also a small sample of a noisy
daily rate.

What is closer to a controlled reading is **rejections falling by a third**.
The fix removed a refusal cause outright — a reply that named no recipient —
so a drop in refusals per day is nearly a direct measure of it rather than
a downstream consequence, and it moves in the direction and roughly the
magnitude the refusal-log count predicted (+36.9% of attempted mail
recovered).

Mail is still far below the 60–120 band, which the affiliation split
already explained: it is the firm's own people who are silent, and nothing
in this fix raises their attempt rate.

## v6 carries a cross-surface fiction about a bug in the engine, and v7 does not

Found by reading the staged file list, not by looking for it. The firm's own
document tree holds `email-recipient-omission-remediation-memo.docx`,
`to-cc-mishap-process-fix.md`, `read-aloud-to-cc-escalation-tracker-policy.docx`
and `huddle-notes-2025-to-cc-policy-bates-trim.md`.

There was no such workplace problem. What the personas were reacting to is
the engine refusing any reply that named no recipient — the defect fixed in
`36984fc`, which cost 37% of attempted mail. They could see mail failing,
so they did what a competent firm would do: wrote a policy, tracked
escalations, and reminded each other to read the To/CC line out loud before
sending.

Measured across the finished 67-day record — **151 of 18,263 on-stage
events, 0.8%**:

    document.created      19 of   451   4.2%
    document.revised      19 of   583   3.3%
    chat.message          29 of  1252   2.3%
    meeting.transcript     4 of   290   1.4%
    email.message          8 of   707   1.1%
    work.time.logged      72 of 11127   0.6%

Someone billed time to it.

**v7 is clean.** Over its first ~7 days and 2,703 on-stage events the same
screen finds *nothing*, against 3 chat hits in v6's first 10 calendar days —
the fiction had already started there by day 10. Removing the refusal
removed the thing the firm was reacting to, which is the only fix that ever
works for this defect class: a persona cannot narrate a failure it never
sees.

**This decides which corpus ships.** v6 is usable for building and probing
a task — everything in this document was measured on it — but it is a
record of a firm that spent six months managing a bug in its simulator, and
1.4% of its transcripts are about that. v7 is the one to grade on.

## `unanswered-question-register` survives the email fix — the pilot was wrong

Recorded earlier in this document: *"the email fix may kill this task rather
than rescue it"*, on a pilot that read 25% unanswered before the fix and 0%
after. That was a small-sample artifact and it is now superseded.

Measured on the two recordings over the **same first 16 calendar days**,
applying the brief's own rule — a body containing `?`, at least one
recipient in To, and no To-addressee replying in the thread within three
working days:

    v6   117 emails    50 asked    25 unanswered   50.0%
    v7   144 emails    58 asked    20 unanswered   34.5%

**Corrected, over a longer span.** Those sixteen days were noise. Measured
through simulated day 43 — the furthest both recordings reach:

    v6   320 emails   135 asked   74 rows  54.8%   late-replied  5  (6.8%)
    v7   357 emails   151 asked   83 rows  55.0%   late-replied 10 (12.0%)

The unanswered rate is **the same on both worlds**, ~55%. The email fix does
not reduce it, and the earlier "cuts it by a third" was a sixteen-day
artefact of exactly the kind this document keeps catching in other people's
numbers.

What the fix *does* move is the thing next to it: **late replies double,
6.8% to 12.0% of rows.** More mail, and threads that develop far enough for
an answer to arrive after the deadline rather than never. That matters for
this task specifically, because its sharpest distinction — a late reply does
not answer the question — is only interesting when late replies exist. At
6.8% it is nearly vacuous; at 12% it has something to bite on. A previous
world read 47%, so the mechanism has been strong before and this world is
still the weak end of it.

Either way the register is not emptied: 83 rows through day 43.

Two caveats, both real. Sixteen days is early, and the two recordings are
different draws once the first action resolves differently — so the *level*
is provisional and only the direction is safe. Over v6's full 68 days the
same screen reads 69.1%, well above its own 16-day figure, so the rate
climbs as threads accumulate; expect v7's to climb too, from a lower base.

The task's premise is re-measured on v7 before it ships, not carried from
here. What is settled is that it has a premise.


## Correction: "23% of announced attachments do not exist" is not supported

Stated above and in a commit message, from the band
`documents.announced_attached_share` reading 0.774 against a floor of 0.9.
Checked, and it does not mean that.

The band counts any email whose body contains `attach` or `enclosed` as a
promise, then returns **total attachments divided by total such emails** —
a ratio of totals, not a per-message rate, so one email carrying three
attachments offsets two carrying none.

Measured properly on the 67-day record: 102 emails use a word that could
announce an attachment and 76 of them carry one, so 26 do not. That per-
message rate (75%) happens to land near the band's 0.774, which is why the
misreading survived.

But the 26 are mostly not false announcements. Reading them:

> "you'll hear it from me directly, with the amendment language attached"
> "I attached the status memorandum earlier for the file"
> "the current version (with all amendments incorporated or attached as
> exhibits)"

— a promise about a *future* message, a reference to a *past* one, and a
description of how a document is assembled. The word is doing ordinary work
in each. The firm is not claiming attachments it did not send; the band
cannot tell an announcement from a mention.

**So this is a defective band, not a defective world**, and it belongs with
the inherited failures rather than the real ones. The lesson is the one this
document keeps relearning from the other side: a number that agrees with a
plausible story is not evidence for the story. I read a ratio of totals as a
per-message rate, got a figure close enough to be unremarkable, and wrote it
down.

## Rate limiting looks exactly like a slow model — and it is not the recording

**Corrected below.** This section first blamed the recording; it is wrong,
and the correction is at the end.

## What the 429s actually are

The third probe's slowest trial carries **six HTTP 429s** in its agent log,
and its output stopped growing for twenty minutes while the other two ran
on. Nothing was wrong with the model or the task: a 180-day recording was
running at concurrency 48 against the same OpenRouter key.

This matters more than an operational annoyance, because of what a starved
trial looks like from downstream. It reads as a model that is slow, gets
less done, and runs out of time — the exact signature the timeout section
above is about, and indistinguishable from it without opening the log and
counting 429s. A benchmark number produced this way is a measurement of
queue depth.

**So: a probe and a recording do not share a key.** Either pause the
recording, or wait for it. When neither is possible, count the 429s in the
agent log before believing the score, and say so beside the number.

Which is also the reading of the recording's own throughput: v7 records at
~4.1 simulated days per hour with probes alongside it, against a documented
~6.2 on its own. Both sides pay.

## `double-booked-week` has no material, by a factor of forty-seven

Measured on the finished v6 record, over the 69 working days its calendar
covers:

    events per working day     4.7    the brief assumes ~47
    genuine clashes            5      in the whole record; the brief assumes
                                      ~3.4 a day, i.e. ~34 rows in a fortnight

The brief's numbers were carried across from another world. This firm holds
about five meetings a working day, scheduled by one docket manager into
non-overlapping slots, and its people are not double-booked because nothing
books them twice. There is no window of a 69-working-day record that
contains 34 clashes when the record contains 5.

Two things worth separating, because the first was my own wrong guess.

**It is not the recurrence gap.** The obvious explanation — recurring series
projected as one event rather than one per occurrence, which would hide most
of the calendar — is false here: 290 meetings reference 290 distinct
calendar events. The calendar has one row per occurrence. The rate really is
five a day.

**It is a premise carried between worlds**, which is this dataset's oldest
mistake and the one that keeps coming back wearing new clothes. The number
was true where it was written. Nobody re-measured it here, and it sat in a
brief looking like a fact about this firm.

Retire it, or re-found it on a mechanism this world has. It is the fourth
task in this dataset to be retired for producing 0–5 rows, and every one of
them was caught by measuring the premise rather than by running the task.

## The staged tasks, premises measured — and two I nearly retired wrongly

Six tasks are staged with unfilled placeholders. Their premises, measured on
the finished v6 record before anyone fills anything:

    task                          material                       verdict
    double-booked-week            5 clashes in 69 working days   DEAD
    court-clock-computation       195 interval-bearing messages  viable
    one-sentence-two-dates        100 two-date sentences         viable
    deadline-week-promise-clock   133 promise+deadline emails    thin
    unanswered-question-register  34.5% unanswered on v7         viable
    prebill-narrative-screen      structured; not at risk        —

**Correction: only two tasks are actually finished.** The build prints a
"staged, not finished" list and I read absence from it as readiness. It is
not: that list catches `«MEASURE` in a brief and `measure("` in Python, and
three tasks use a third form — a module constant left as `None` that the
solver refuses on. Run each solver and the real state is:

    off-sense-register            runs
    live-commitment-register      runs
    unanswered-question-register  STAGED
    no-op-revision-register       STAGED

Absence from a list is not presence on another one, and a check that
enumerates two of three shapes reports the third as fine.

`deadline-week-promise-clock` is thin rather than dead, and the fix is
measured. **Re-measured with the brief's own seven forms rather than my
proxy** — its rule has no promise conjunct at all, it is the form alone —
223 messages carry an admitted form, 3.3 a day: one week yields 9 rows,
a fortnight 32-34. And three of the seven forms are dead on this corpus:
`end of month` fires on 0 messages, `by <Month> <day>` and `within N days`
on 1 each. The table has to lose them.

The proxy figures below (which required a promise phrase) are kept for the
record and are not the task's numbers: 148 promise-and-deadline emails over
68 recorded days, windowed:

    calendar days  0-6     5 rows, 4 senders     under the floor
    calendar days  0-13   24 rows, 11 senders    clears it
    calendar days  7-20   29 rows, 11 senders
    calendar days 21-34   29 rows, 14 senders

The one-week window its brief describes yields **five rows**; a fortnight
yields 20-29 from 10-14 different people. Widen it to two weeks and say
"fortnight" in the brief rather than leaving the name to imply seven days —
the task's title is a label, not a specification, and this dataset has
already shipped one register whose window nobody re-derived.

**And the part worth writing down is that I got two of these wrong first.**

My first screen for `one-sentence-two-dates` matched only calendar dates —
`March 14`, `3/14` — and returned **zero** sentences carrying two. I was one
commit away from retiring the task. Widened to what this firm actually
writes, which is weekdays and relative forms, it returns **100**:

> "I'm free tomorrow after 2:00 or Thursday before 11:00"

The same happened to `court-clock-computation`: a narrow interval pattern
found 12 messages, a fair one finds 195.

This is the gate-drift defect from the other side. A screen whose pattern is
narrower than the corpus's vocabulary reports material as *absent*, and
absence is the verdict nobody argues with — it retires a task quietly and
looks like diligence. The rule that catches it is the one already applied to
`live-commitment-register`'s deadline table: **before believing a screen
that says nothing is there, check what the corpus writes instead.**

`double-booked-week` survives that check and stays dead, because its
measurement is not a pattern match at all: two events clash when their time
ranges overlap, which is arithmetic. Five is five.


### Correction: the recording was not the cause

The section above concluded "a probe and a recording do not share a key",
from six 429s in a starved trial while a 180-day recording ran at
concurrency 48 against the same key. Tested by pausing the recording and
re-running the probe on an otherwise idle account.

    with the recording, ~75 minutes in     6, 8, 10 429s   ~0.10 / minute
    recording paused, ~25 minutes in       5, 5,  6 429s   ~0.22 / minute

Pausing it did not help, and per minute it is worse. **The 429s come from
running three Opus trials concurrently on this account, not from sharing
with the recording.** The recording may add to them; nothing here shows it
does.

What survives is the part that mattered: **a rate-limited trial is
indistinguishable downstream from a slow model** — less done, out of time,
zero — and the only way to tell is to open the agent log and count 429s.
Do that before believing a score, and report the count beside it. What does
not survive is the causal story I attached to it, which I reached by
noticing one plausible cause and stopping.

The operational consequence I drew from that — probe at lower concurrency —
**is also wrong**, and tested:

    k=3, recording running     6, 8, 10 429s
    k=3, recording paused      5, 5,  6 429s
    k=1, recording running     5 429s in the first four minutes

A single trial on an idle account still hits them. So the 429s are ambient
on this account for this model, at any concurrency, with or without a
recording, and the harness retries through them — the one trial that ever
completed did so *with* 429s in its log.

**I have now been wrong twice about the cause and will stop guessing.** What
is established, and all that is: 429s are present in every probe here; they
are not caused by the recording; they are not caused by concurrency; and a
trial can complete despite them. The binding constraint on this task is the
wall clock, not the rate limit.

What survives from the original section is the only part that was ever
measured: **a rate-limited trial is indistinguishable downstream from a slow
model**, so count the 429s in the agent log and report the count beside any
score. Everything else here was a story fitted to one observation, twice.

## `prebill-narrative-screen`: the word family, measured

The brief asks its filler to choose a word family from the *narratives* —
a different corpus from mail, with its own vocabulary — on three tests: both
forms must fire, each must match entries the other does not, and the
off-sense share must be high, because that is what a model reading for
meaning throws away while a textual screen keeps it.

Run over all 11,127 time-entry narratives on the v6 record:

    family              form A   form B   A only   B only   both
    review/reviewed        788     3207      718     3137      70
    draft/drafted          347     1304      334     1291      13
    file/filed             274      227      265      218       9
    close/closed            75       93       75       93       0
    update/updated         197      841      197      841       0
    revise/revised           2      494        2      494       0

`review` and `draft` fire far too widely — 3,995 and 1,638 entries, a third
and a seventh of the firm's timekeeping. `revise` and `prepare` fail the
first test outright: 2 and 0.

**`file` / `filed` is the family.** 492 entries between them, 4.4% of the
corpus, each form matching hundreds the other does not — and the off-sense
share is the reason:

    file    274 entries    47% noun-sense
    filed   227 entries     0% noun-sense

Nearly half of `file` is the *thing*, not the act — "Reviewed Cotswold
Mutual claims **file**", "Drafted **file** memo", "for the **file**" — while
`filed` is always the act. A reader screening for the idea of *filing* drops
about half of one form and none of the other, which is exactly the split
`off-sense-register` gets from `agree`/`agreed` in mail, reproduced in a
corpus that needed its own measurement rather than the mail figures carried
across.

## The window is set by what an agent can finish, not by what the corpus holds

Nine trials across three probes, all at days 42–88 — 143 standing meetings,
726 turns, 53,960 words — and **not one wrote a deliverable**. The only
trial that ever finished was the very first, under the *less precise* brief,
and that is the clue: a vague brief makes an agent guess and stop early; a
precise one makes it calibrate, and calibration is what ran out of time.
Making the brief better made the task longer.

Raising the budget from 3600s to 5400s did not fix it, and lowering
concurrency from k=3 to k=1 roughly doubled throughput without closing the
gap. So the window is the thing that has to move.

Re-measured, the alternatives on the same record:

    window        mtgs   words   rows  sup%  floor
    days 42-88     143  53,960     33   61%   12%
    days 42-81     123  46,471     30   57%   20%
    days 49-74      83  31,539     25   52%   16%
    days 42-67      80  29,706     24   46%   17%

**Days 49–74 ships** — Monday 23 February to Friday 20 March, 20 working
days. It costs 8 rows and 9 points of supersession against the largest
window, and buys back 42% of the reading. Every screen still passes: 25 rows
over a floor of 12, 52% supersession over a floor of 15%, 31,539 words under
a ceiling of 60,000, and a guessing floor of 16%.

**The general point, and it is not about this task.** A window sized by what
the corpus can support is sized by the wrong constraint. The binding one is
what a careful agent can *finish* — and that is not knowable from the
corpus, only from a probe. Three probes and nine trials bought this number;
no amount of reading the transcripts would have.

## The measurement, reproduced on a second window

`opus-5`, k=1, days 49–74 (83 standing meetings, 429 turns, 31,539 words,
25 oracle rows), 5400s budget. It finished inside the budget, which is what
the smaller window was for.

    meetings_read        83 / 83      exact
    turns_read          429 / 429     exact
    distinct_owners      11 / 15
    superseded_count     22 / 31
    rows                 17 / 25      8 matched     row_f1 0.381
    pairs, ignoring the date          16 / 25

Composite, at the weights `tests/criteria.py` pins (row_f1 5, row_facts 3,
three paid scalars at 1): **≈ 0.40**, inside the 0.2–0.8 band.

**It reproduces.** The first probe, on a different window (days 42–88, 33
rows) and an earlier brief, read `row_f1` 0.364 with the same shape:
`meetings_read` and `turns_read` exact, about two thirds of the pairs found,
about half of those dated wrong, `superseded_count` short. Two windows, two
briefs, the same answer — this is a property of the task, not of one draw.

**Where it loses is where the design put it.** The reading is perfect: every
meeting opened, every turn counted. What it cannot do is resolve each
relative deadline against the right meeting and notice the later mention
that moved a date. Of the 16 pairs it correctly identified, 8 carry the
wrong date — a coin flip on the field the whole design turns on.

**And the grading fix earns its place here.** `row_facts` on this answer is
0.16. Under the old penalty bound it would have been 0.000, because the 9
rows keyed differently would have out-weighed the 8 correct ones — wiping
out, on a criterion worth 3 of 11, an answer that got a third of the
register exactly right. That would have read as 0.29 instead of 0.40, and
the difference is entirely arithmetic rather than comprehension.

## The task discriminates on tool strategy, not only on reading

`glm-5.2`, same window, same brief, same 5400s. It read the corpus a
different way, and the difference is stark:

    model      shell calls   MCP tool calls   output      deliverable
    opus-5          56-72             2-4     1.28 MB     written
    glm-5.2             4             452     2.30 MB     written

(Corrected: glm made **four** shell calls, not zero — my first count used a
pattern that did not match this log's shape. The lopsidedness is the point
and it survives: 452 tool calls against 4.)

**Opus dumps the window with the shell and spends its budget on judgement.
glm pages the same 83 meetings one transcript at a time through the MCP
tools and spends its budget on retrieval.** That is why its log is nearly
twice the size while containing less work: most of those bytes are
transcript payloads coming back through the tool boundary, one call at a
time, 448 times.

**It did write a register, in its last minutes** — I wrote "it never wrote
one" here while the trial was still running, which was true at the time and
not a fact about the run. The correction and the score are below.

This is worth separating from "glm is weaker at reading", which the run does
not show. What it shows is a strategy difference with an enormous cost
attached, on a corpus that is 31,539 words — small enough to hold, large
enough that fetching it a piece at a time consumes an hour and a half.

**Whether that is difficulty or an artefact is a fair question**, and the
answer here is that it is the task working as designed. The environment
gives every model the same shell and the same tools; the brief names
neither. Choosing how to get 83 transcripts in front of yourself *is* part
of the work, and a model that spends its whole budget on retrieval has made
a real mistake about a real trade-off, not been tripped by a harness quirk.
Both models had 5400 seconds and the same corpus.

It does mean a score of 0.00 here should be read as **"never got to the
question"**, not as "answered it badly" — and the two are worth reporting
separately, because a suite that cannot tell them apart will retire a task
for being too hard when it is really too slow to reach.


## The discrimination curve, measured

Both models, same window (days 49–74, 83 meetings, 429 turns, 31,539 words,
25 oracle rows), same brief, k=1, 5400s.

    criterion            weight   opus-5    glm-5.2
    meetings_read           1      1.000      1.000
    turns_read              1      1.000      1.000
    live.f1                 5      0.381      0.229
    row_facts               3      ~0.16      0.060
    superseded_count        1      0.000      0.000
    ------------------------------------------------
    answer                         ~0.40      0.302
    process                         0.50       0.50

    rows submitted                 17 / 25    10 / 25
    superseded_count               22 / 31     6 / 31
    distinct_owners                11 / 15     8 / 15

**Read these against the floors, not against zero.** An empty register
scores **0.273** on this task — the two paid scalars that measure *reading*
are free to anyone who opens the window. So the useful signal is what sits
above that floor: opus **+0.13**, glm **+0.03**. Opus does roughly four
times the gradeable work, on a scale where the raw scores look close.

**Both read the whole corpus.** `meetings_read` and `turns_read` are exact
for both — this task does not discriminate on coverage, and never did. It
discriminates on what a model does with the corpus once it has it.

**Both under-report, neither invents.** Opus submits 17 rows and glm 10,
against 25, and `failure_analysis` flags the pattern: *missing rows with
none invented often means a filter the instruction states differently from
the oracle*. Worth taking seriously rather than reading as model failure —
though after the owner-form correction, both models are now applying a rule
the brief states as a closed set, and the residue is that neither finds
every turn that satisfies it in the time available.

**`superseded_count` is the cleanest separator and both fail it.** 22 and 6
against 31. It is graded exact, and it is the one figure that cannot be
reached without crossing meetings — which is the mechanism this task exists
to grade.

## The oracle was wrong and the models were right

The most important result of the probe sequence, and it came from checking
the misses instead of banking the score.

`failure_analysis` flagged the pattern: *missing rows with none invented
often means a filter the instruction states differently from the oracle*.
Both models under-reported heavily — 17 and 10 rows against 25 — and
neither invented one. Reading the nine rows Opus never found settled it:

> **Ingrid** — *"the second I get a timestamped response from their counsel
> I'll log it straight into the tracker"*. A real promise, conditional on an
> external event, with no date of its own. The `EOD tomorrow` sat two
> sentences away, describing a checkpoint.
>
> **Thandiwe** — *"Position Statement review, owner Jamal, due EOD tomorrow
> ... I'll circulate the updated Master Docket Report"*. The docket manager
> reciting somebody else's deadline beside an undated promise of her own.
>
> **Gideon** — *"if it's still open Wednesday EOD, flag me directly and I'll
> make the call"*. The date is the condition, not the deadline.

**Eight of twenty-five oracle rows were of this kind, and both models
declined all of them.** The row count under a sentence-scoped rule is 17 —
exactly what Opus submitted.

**It is the defect that retired this task's first design, one conjunct
over.** I removed the matter column because "which piece of work a promise
is about" is clause-scoped while speaker and deadline are turn-scoped — and
then left owner and deadline paired at turn scope, where they are *both*
present but not necessarily *together*. Both being properties of a turn does
not make their pairing one.

### What the score actually is

    against the oracle at each stage of my own fixing
      ambiguous brief, turn-scoped, broken row_fields   0.347
      brief fixed, row_fields fixed, still turn-scoped  0.40
      sentence-scoped                                   0.495
      sentence-scoped + the full compound table         0.529

`row_f1` 0.588, 10 of 17 rows exact, `superseded_count` 22 against 15.
**0.529 is the honest number** and the earlier ones were measurements of my
own artefacts. It is still inside the band, and it still loses where the
design intends: the reading is perfect and the date resolution is not.

### Two more compounds, found by the same test

Fixing the rule surfaced two more forms the table did not know, both naming
one day and both resolving a day early without it: **`tomorrow EOD`** (27
turns) and **`<weekday> EOD`** (6). With `EOD tomorrow` at 79 turns, the
compound family is 112 turns — a quarter of everything the register grades.
Order is the rule: every compound, in either direction, ahead of either
part.


## The curve, against the corrected oracle

Both deliverables re-scored against the sentence-scoped oracle with the full
compound table. glm's register was recovered from its agent log, which had
printed the file back; the trial's artefacts kept only logs.

    model     rows   matched   row_f1   row_facts   superseded   ANSWER
    opus-5   17/17        10    0.588       0.294      22 / 15    0.529
    glm-5.2  10/17         6    0.444       0.176       6 / 15    0.432

    floors:  empty_register 0.273 · reported_every_candidate 0.444 · nothing 0.000

Above the empty-register floor — the honest denominator, since the two
scalars that measure *reading* are free to anyone who opens the window —
opus is **+0.256** and glm **+0.159**. Opus does about sixty per cent more
gradeable work on a scale where the raw numbers sit a tenth apart.

**The two fail differently, and that is the useful part.** Opus reports
*exactly* 17 rows against 17 and gets 10 of them right: it finds the
register and misses on dates. glm reports 10 and gets 6: it under-finds. And
`superseded_count` separates them cleanly in the other direction — opus
over-counts at 22, glm under-counts at 6, against a true 15. Neither reaches
it, which is the mechanism the task exists to grade.

Both sit inside the 0.2–0.8 band on a task whose wrong branches score 0.444
and 0.273. That is the result the design was aiming at.

**Half of it, measured properly (2026-08-22).** The paragraph above takes
`empty_register` 0.273 as the denominator, and that is the weaker of the two
no-comprehension strategies. The stronger one — report every candidate — is
a *bracket*, not a point: 0.171 with its own counts wrong, 0.444 handed the
oracle's scalars for free. Against the top of that bracket:

    opus-5   0.529   +0.085 above a dump
    glm-5.2  0.432   -0.012, i.e. AT OR BELOW it

So the design achieved one of its two aims and not the other. It moved a
frontier model off 1.000 *and* clearly above indiscriminate reporting,
which is the thing this dataset had never managed before and which the
per-route repeat supports: 0.543 and 0.536 by different routes, sd 0.004,
against a 0.444 ceiling on dumping — a gap of roughly twenty standard
deviations. **glm's 0.432 is not evidence that glm did anything.** It is
what reporting every candidate scores, to within a hundredth, and the
"+0.159 above the empty-register floor" above flatters it by choosing the
easier baseline.

That the two *fail differently* — opus over-counts supersession at 22, glm
under-counts at 6 — remains true and remains the useful part. It is a
statement about the shape of their errors, not about their scores clearing
a floor.

The same analysis applied to ashgrove found no task where any model clears
its dump bracket; see that dataset's `DIFFICULTY.md`. The contrast is the
point: this task discriminates a frontier model from a dumper and that one
does not, so the measurement is not merely destructive.

## Premise audit complete: all eight tasks measured on the finished v6

    task                          material on v6                    verdict
    live-commitment-register      17 rows, 52% supersede            BUILT, 0.529/0.432
    off-sense-register            88 hits; 109 stem-only decoys     viable
    court-clock-computation       195 interval-bearing messages     viable
    one-sentence-two-dates        100 two-date sentences            viable
    unanswered-question-register  34.5% unanswered (on v7)          viable
    prebill-narrative-screen      file/filed, 492 entries, 47% off  family chosen
    deadline-week-promise-clock   5 rows/week, 24 per fortnight     widen to 2 weeks
    double-booked-week            5 clashes in 69 working days      DEAD

`off-sense-register`'s decoy structure is exactly what its brief claims, and
worth recording because the claim is load-bearing: 88 messages carry an
admitted form, and **109 carry `agreement`/`agreements` with no admitted
form at all**. A reader who stems to `agree-` takes on more messages than
the register contains, so the mistake does not shade the answer — it swamps
it. Ninety-five more carry a synonym (`sign`, `signed`, `align`, `consent`)
and stay out.

**One dead, one to widen, six sound.** Every verdict is a measurement on the
record rather than a reading of the brief, and two of them reversed a first
answer: `one-sentence-two-dates` and `court-clock-computation` both read as
empty under a screen narrower than the corpus's vocabulary.

## v7 validated on a larger sample: the fixes hold

Measured at v7 day 31, against v6 truncated to the same simulated span
(~calendar day 43) so the comparison is like-for-like.

**The engine fiction is gone.** The screen that found 151 events in v6's
full record finds, over the matched span:

    v6   16 hits of 9,197 on-stage events   (chat 8, time entries 6,
                                             documents 1, email 1)
    v7    0 hits of 8,727 on-stage events

Zero, across four surfaces that all carried it before. Removing the refusal
removed the thing the firm was reacting to.

**The file room resolves completely.** 201 served paths, 201 files, **100%
of served paths open**, and the depth histogram shows real folders —
187 of 201 four levels deep. v6 served 374 of 377 paths at locations that
did not exist.

**Volume, same span** — and read this cautiously:

    email.message        320 -> 357   1.12x
    meeting.transcript   135 -> 143   1.06x
    document.created     214 -> 201   0.94x
    calendar.response    591 -> 517   0.87x
    chat.message         670 -> 503   0.75x

**Correcting an earlier figure of mine.** At v7 day 7 this document recorded
email at 1.58x. Over 43 days it is 1.12x. The first number was seven days of
a noisy daily rate and should not have been written down as a ratio at all;
chat moving to 0.75x on a surface the email fix cannot touch is the standing
reminder that these are different draws, not an intervention effect. What
the email fix is measured to do is recorded where it can be: the refusal log,
and refusals per day falling by a third.

## Variance: two Opus samples, 0.543 and 0.536

Same window, same brief, same budget, scored against the same oracle.

    sample 1   17 rows, 10 matched, row_f1 0.606, superseded 22/13   0.543
    sample 2   11 rows,  8 matched, row_f1 0.593, superseded  7/13   0.536

    mean 0.539   sd 0.004

The scores are almost identical and the *routes* are not: one reports 17
rows and matches 10, the other reports 11 and matches 8, and they miss
`superseded_count` from opposite sides — 22 against 13, and 7. A task that
returns the same number from two different mistakes is measuring something
stable about the model rather than the luck of a draw.

**n=2, and honestly so.** Three trials were launched; one never wrote a
register inside 5400s and one was still calibrating when the budget ended.
That is the k=3 behaviour recorded above — concurrency roughly halves
per-trial throughput on this account — and it is why the useful sampling
strategy here is k=1 repeated rather than k=3 at once.

Taken with glm-5.2 at 0.443, the picture is a task where two model tiers
land a tenth apart, both inside the 0.2–0.8 band, on wrong branches of 0.442
and 0.273.

## Correction: `court-clock-computation` is dead, and my screen was too broad

Recorded above as viable on **195 interval-bearing messages**. Wrong. That
pattern matched any `N days` construction anywhere in mail or chat, and most
of its hits were the docket tracker's own *"N days remaining"* — not a court
clock at all.

Measured against the three forms the brief actually admits, over 1,959 mail
and chat bodies in the 67-day record:

    within N days     1 message
    N days after      1
    due in N days     2
    ANY of the three  4          — 0.06 a day

The best window gives **3 rows against a twelve-row floor**. Widening to
`in N days` (3) and `N days from` (5) reaches about a dozen over six months,
still under the floor, and only by admitting forms the brief does not.

**Both directions of screen error have now bitten the same audit.** Earlier
in this document a pattern *narrower* than the corpus's vocabulary reported
`one-sentence-two-dates` as empty, and I was a commit from retiring a task
with 100 candidates. Here a pattern *broader* than the brief reported a dead
task as viable, and it would have been filled.

The rule that catches both: **screen with the task's own admitted forms, not
with an approximation of them.** A proxy pattern answers a different
question, and which way it errs is luck.

Two tasks now retired on measurement: `double-booked-week` (5 clashes
against ~235 needed) and this one.

## `one-sentence-two-dates` has no material either, and its own table made it look otherwise

Over 707 email bodies in the 67-day record, **14 sentences carry two or more
of the forms its table admits**. Thirteen of the fourteen are a single date
written as a compound:

> *"get you both figures **by tomorrow EOD**"*
> *"You'll have the exposure number **by Wednesday EOD**"*

`by tomorrow` and `EOD` are two rows of the table and one deadline in the
world. The table counts them twice, so the register reports two dates where
the writer named one — and one of the two (today) is a date the sentence
does not mean. The fourteenth, *"back to me by Wednesday close of
business"*, is the same thing in longer words.

**Sentences genuinely naming two different dates: zero.**

This is the compound defect that cost the transcript task a quarter of its
graded turns, met from the opposite side. There a compound resolved to the
wrong day; here it *manufactures the row*. A form table must place every
compound ahead of either of its parts — and once this one does, the task has
nothing left to grade.

**Three tasks now retired on measurement**, and each one looked fine until
it was counted with its own admitted forms:

    double-booked-week        5 clashes against ~235 needed
    court-clock-computation   4 messages carry any admitted form
    one-sentence-two-dates    0 sentences carry two real dates

That is three of eight. The remaining five are `live-commitment-register`
(built, probed, 0.54/0.44), `off-sense-register` (88 hits, decoys verified),
`unanswered-question-register` (34.5% on v7), `prebill-narrative-screen`
(family measured), and `deadline-week-promise-clock` (223 messages, needs a
fortnight and four of its seven forms dropped).

## `no-op-revision-register`: viable, but its trap is not on this world

1,034 document versions in the 67-day record; **42 carry an admitted
phrase**, distributed very unevenly:

    no changes made            27      no changes were made      2
    no substantive changes     11      no edits made             1
    no substantive edits        1      no substantive revisions  0

Two things follow. `no substantive revisions` grades nothing and should go
unless the finished record writes it — the same defect as three of
`deadline-week-promise-clock`'s seven forms.

And **the decoys the brief names do not exist**. `only formatting`,
`typo fix`, `minor cleanup`, `nothing material`, `cosmetic only`: zero each,
across 1,034 comments. The brief spends a paragraph excluding them and the
difficulty it claims from them is imaginary here. The one genuine near-miss
the corpus offers is the singular `no substantive edit`, twice, which the
asymmetry rule already shuts out.

The window: 2 rows in a fortnight, 14 in four weeks, 20 over days 14–41.
**Four weeks is the minimum** that clears the twelve-row floor, against 329
versions to read.

That completes the audit of all nine task directories. Every verdict is a
count against the task's own admitted forms — the discipline that reversed
two of them in each direction.

## The third tier could not be measured, and its 0.000 is not a score

`gpt-5.6-sol`, same window and brief, returned **reward 0.000** — and that
number is a fact about this account, not about the model. Its agent log
carries **108 HTTP 401s, one 403, and eighteen "your API key was rejected
by the provider"**, with the provider's own hint: *does your account have
access to `openai/gpt-5.6-sol`?*

Nine of its tool calls succeeded before the wall, and its reasoning shows it
had understood the task — it was working out how to fetch 83 transcripts
efficiently, the same strategic question that separated the other two tiers:

> *"I wonder if I can programmatically call MCP? Since execute_code cannot
> handle tool calls directly, I could run individual calls in parallel."*

**So the Pareto has two points, not three**, and saying otherwise would put
a harness failure on a difficulty curve. This is the same rule the timeout
and rate-limit sections above are about, arriving a third time and from the
cheapest possible direction: *a zero is a claim about a model only once you
have ruled out every way the harness can produce one.* Counting 401s takes
a minute; a fabricated third point would have survived indefinitely.

The tier stays in `scripts/rollout.py`'s table because the gateway resolves
it correctly — what is missing is entitlement on this account, which is not
something a dataset can fix.

## v7 at day 42: the vocabulary has changed worlds

`scripts/measure_new_corpus.sh` run against the live recording:

    file room        252/252 served paths resolve (100%)
    engine fiction   0 of 11,315 on-stage events — clean
    transcripts      188 meetings, 956 turns, 70,496 words
    supersession     61% any mention / 56% speaker's own commitment
    guessing floor   'monday', 28% of live answers

**On v6 the modal deadline token was `eod` at 68%. On v7 it is `monday` at
28%.** Same engine, same workplace spec, same seed — a different draw, and
the deadline vocabulary is not the same shape. A window chosen from v6's
numbers would have been chosen against a distribution this world does not
have, and the guessing floor alone moves by forty points.

That is the concrete case for the instruction every brief's `«MEASURE»` note
now ends on: **re-count here, do not carry over.** It is also the third time
this document has caught a number travelling between worlds — after the
`deadline-week-promise-clock` article ratio (15-to-0 claimed, 149-to-0
measured) and `double-booked-week`'s event rate (47 a day assumed, 4.7
measured).

The two structural fixes hold at scale: the file room resolves completely
where v6 served 374 of 377 paths at nothing, and the engine fiction that ran
through four of v6's surfaces is absent from 11,315 events.

## v7's behavioural defects, characterised for the next engine pass

The structural fixes hold (file room 100%, engine fiction 0). The
*behavioural* bands do not, and v7 carries every one v6 had. Measured at day
46 on 26,546 events:

    calendar.rsvp_needsaction   0.772   against ≤ 0.1      (v6: 0.666 — worse)
    calendar.rsvp_accepted      0.223   against 0.6–0.8
    calendar.rsvp_tentative     0.000   against 0.05–0.15
    calendar.rsvp_declined      0.004   against 0.05–0.15
    calendar.cancellation_share 0.000   against 0.03–0.08
    email.per_day              10.96    against 60–120
    email.thread_depth_median   1       against 1.5–3

The firm still has **one RSVP verb**, still never cancels a meeting, and
still writes a tenth of the mail a firm this size would.

**Two the earlier audit did not name, both sharp enough to fix directly.**

**Only 19% of the firm's mail is internal.** Split by affiliation over 674
recipient-pairs:

    external -> internal   333   49.4%
    internal -> external   211   31.3%
    internal -> internal   130   19.3%      band wants 45–65%

Half the firm's inbox is its clients writing in. Colleagues barely write to
each other, which is the "the firm is silent" finding from v6 in its sharpest
form — and it bounds any task keyed on internal correspondence.

**Replies are instantaneous.** Median latency between consecutive messages
in a thread is **0.08 hours — five minutes** — against a band of 1.5–6
hours, and the distribution is not a distribution:

    under 5 minutes   176 of 333   53%
    under 1 hour      197          59%
    under a day       246          74%
    p90                            126 hours

Half of all replies land inside five minutes and the tail runs to three
weeks. That is not lognormal, it is two populations: a persona answering
inside the same wake it received the message, and one that never gets back
to it. The fidelity band says the same thing less legibly —
`reply_latency_lognormal_p 2.9e-30`.

The five-minute cluster is worth fixing before a task is keyed on timing —
though **not for the reason I first wrote here.** I claimed the three-
working-day threshold in `unanswered-question-register` "is doing no work at
all". Counted, it is doing some. Of 233 questions with a To recipient on v7:

    under 10 minutes      68   29.2%
    10 minutes – 1 day    15    6.4%
    1 day – the deadline  16    6.9%   <- decided by the window
    after the deadline    12    5.2%   <- the brief's "late does not count"
    never answered       122   52.4%

**12% of questions sit in the zone where the exact rule matters**, and that
is what separates the register from the naive "did anybody ever reply"
list — a difference of about one row in eight, which is real and modest.
The other 88% are settled at ten minutes or never.

So the task's distinction survives, and the honest description of this world
is that it answers fast or not at all: **52% of questions are never answered
by anyone in To**, and 29% are answered before a human could have read them.
Both halves are engine behaviour rather than firm behaviour, and both bound
what a timing-keyed task can measure here.

## The whole firm wakes at the same moment, and the code that should spread it computes zero

The sharpest engine finding of this pass, and the cause of the reply-latency
defect above.

Measured on v7: **21 personas, 323 distinct wake timestamps, and every
single timestamp has all 21 of them on it.** 09:00, 10:30, 12:00, 13:30 —
the entire firm acts in lockstep, seven times a working day, and nothing
happens in between.

The cause is four lines in `grounded.py` that exist precisely to prevent it:

    quantum = max(grid, -(-interval * 60 // grid) * grid)
    slots   = quantum // grid
    phase   = derive_seed(seed, "wake-phase", day, entity) % slots
    wake    = day_start + phase * grid

With `wake_grid_minutes` at 90, any persona whose check interval is **at or
below 90 minutes** gets `quantum == grid`, so `slots == 1`, so
`phase = seed % 1 = 0`. Every persona. Every day.

    interval  30 min -> quantum  90, slots 1, phase ALWAYS 0
    interval  60 min -> quantum  90, slots 1, phase ALWAYS 0
    interval  90 min -> quantum  90, slots 1, phase ALWAYS 0
    interval 120 min -> quantum 180, slots 2, spread

A seed derivation, a modulo and a multiply, all executing, all incapable of
returning anything but zero in the configuration actually used. This is the
`capability without a caller` class in its subtlest form yet: the code is
not dead, it is *inert* — it runs on every persona on every day and computes
a constant.

**What it explains.** Three failing bands stop being separate problems:

* `email.reply_latency_median 5 minutes` against 1.5–6 hours — a message and
  its reply land in the same tick, because there is no later tick to land in
  until 90 minutes have passed.
* `slack.offhours_share 0.034` against ≥ 0.15 — there are no off-hours
  ticks, so there is no off-hours anything.
* `email.thread_depth_median 1` — a thread advances at most once per tick
  per participant, and all participants share the tick.

**The fix is small and the decision is not.** Deriving the phase over a
finer sub-grid — minutes within the quantum rather than grid-multiples
within it — spreads 21 personas across 90 minutes instead of stacking them
on one instant. But `grounded.py` is inside `_ENGINE_SURFACE`, so changing
it means v7 cannot be resumed: the recording is at day 47 of 180, about 16
hours from finishing, and a fresh run is about 29. **Roughly 13 hours to buy
a firm with temporal texture.**

Recorded rather than acted on, because that is a resource decision rather
than a correctness one, and because the fix should be piloted over two days
before 29 hours are spent on it. What is *not* in doubt is the diagnosis:
323 timestamps, 21 personas on each, and a phase that is arithmetically
pinned to zero.

### The fix, piloted

Applied in an isolated git worktree so the running recording's tree was
never touched, and run as a real 3-day recording rather than reasoned about:

    slots = max(1, quantum // PHASE_STEP)      # PHASE_STEP = 60 seconds
    wake  = day_start + phase * PHASE_STEP

Spreading the phase over *minutes inside the quantum* instead of
*grid-multiples inside it* gives every persona a distinct offset.

    v7 (current)   323 timestamps, 21 personas on every one
    pilot           45 timestamps, ONE persona on 43 of them

The recorded wake times read 09:01, 09:13, 09:14, 09:20, 09:24, 09:34,
09:44, 09:49 — a firm arriving at its desk over the morning instead of a
klaxon going off seven times a day.

**One methodological note worth keeping**, because the first pilot run
measured nothing and looked fine. The worktree symlinks the main
repository's `.venv`, whose `workbench.pth` points at the *main* tree's
`src` — so the pilot imported the unpatched engine and faithfully reproduced
the lockstep it was meant to fix. It took `PYTHONPATH` on the worktree's own
`src` to load the patched module, and the tell was that the "after" numbers
were identical to the "before" ones. A pilot that reproduces the defect
exactly is not evidence the fix failed; check what it imported first.

### And the reply latency did not improve — my causal claim was wrong

The section above says the lockstep "explains" the five-minute reply
latency. **The pilot refutes that.** With wakes fully spread — one persona
per timestamp instead of 21 — the latency is unchanged:

    v7 (lockstep)   median 0.08h,  53% of replies under 5 minutes
    pilot (spread)  median 0.08h,  11 of 12 replies under 5 minutes  (n=12)

The arithmetic says why, and I should have done it before writing the
explanation:

    21 personas over a 90-minute quantum = a wake every 4.3 minutes

Lockstep puts every persona 0 minutes from the next one; spreading puts them
4 minutes apart. **Neither produces a latency measured in hours.** The
binding constraint is that somebody is always about to wake, and a persona
answers at its first opportunity — not that they all wake together.

So these are two defects, not one:

* **the lockstep** is real, is fixed by the phase change, and is what
  `slack.offhours_share 0.034` and the firm's missing temporal texture are
  about;
* **the five-minute reply** is separate and is not addressed by it. Fixing
  it means a persona *declining* to answer at its first opportunity — a
  response delay drawn per message — which is a behaviour change, not a
  scheduling one.

`n=12` is a small sample and the pilot was still running; the point stands
on the arithmetic rather than the count.

**This changes the restart recommendation.** Thirteen hours of recording
would buy the temporal spread and *not* the reply timing, so it buys less
than the section above implied. My inclination is now to let v7 finish and
carry both fixes to a v8 where they can be piloted together — but that is
still a call to make with the numbers, not a conclusion I should reach for
the reader.
