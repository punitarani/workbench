# What to do when the recording finishes

Written at day 30 of 130 with everything corpus-independent complete, so the
work resumes from the blocking condition rather than from whatever was most
recently on someone's mind.

> **REVISED 2026-08-21 for the sixth recording (`epoch-v6`).** Everything
> below was written for `out/merrick/epoch/`, a world since replaced. That
> world's engine wrote its own validation errors into personas' memories,
> lost 85% of the firm's document authoring, served 304 of 308 documents at
> paths that did not exist, and reached nobody with a single calendar event
> or meeting transcript. Six defects, all fixed; see the commits between
> `cece3fb` and `990f56a`.
>
> **Read every path below as `out/merrick/epoch-v6/`.** The old world is
> kept only for before/after measurement and its band gate refuses it
> outright, which is correct — it is a pre-fix world.
>
> Four things changed that this file did not previously know:
>
> 1. **A sixth surface.** `meetings` serves the transcripts, which nothing
>    ever served: 723 of them, 255,889 words, ~30% of everything anyone at
>    the firm said. It is the only corpus here a shell cannot flatten, and
>    a sixth task, `live-commitment-register`, is built on it.
> 2. **`scripts/export_world_log.py` exists**, so the store-to-log recovery
>    described below is a command rather than a snippet — and it is safe
>    against a *running* recording, which is what makes step 0 possible.
> 3. **Step 0 is new and is the highest-value step in this file.** See
>    below.
> 4. **The five tasks are six**, and `deadline-week-promise-clock`'s form
>    table is five rows, not four — measured on v6, not carried over.

## If the recording dies before it finishes

Resume needs the seven files in `_ENGINE_SURFACE` to hash to what the run
recorded — `resume_workplace` refuses a fingerprint change, which is the
guard that stops a world being spliced out of two rule sets.

Those files were reformatted after the run started, so the working tree no
longer matches. **The exact bytes are `git checkout 94e6cc2 -- <the seven
files>`**, which restores fingerprint `a50dae98eb2fe0e5`. Resume, then
`ruff format` them again and commit; nothing else in the tree depends on
their whitespace.

Verify before resuming:

```bash
uv run python -c "import sys; sys.path.insert(0,'src'); \
  from simulation.run import engine_fingerprint; print(engine_fingerprint())"
# must print a50dae98eb2fe0e5...
```

If the run is unrecoverable, `scripts/export_world_log.py` rebuilds
`world.jsonl` from `run.db` and nothing is lost but the unrecorded days.

## Step 0 — measure the recording BEFORE it finishes

Do this at about day 25. It is the cheapest step here and it caught more
than the rest of this file combined.

```bash
mkdir -p /tmp/v6 && cp out/merrick/epoch-v6/run.db /tmp/v6/
uv run python scripts/export_world_log.py --out /tmp/v6
uv run python -c "import sys; sys.path.insert(0,'src'); from pathlib import Path; \
  from core.worldlog import read_events; from tools import project_all; \
  project_all(tuple(read_events(Path('/tmp/v6/world.jsonl'))), Path('/tmp/v6/state'))"
WORKBENCH_STATE=/tmp/v6/state uv run python datasets/merrick/measure_transcripts.py
WORKBENCH_STATE=/tmp/v6/state uv run python datasets/merrick/measure_promise_week.py
WORKBENCH_STATE=/tmp/v6/state uv run python datasets/merrick/measure_word_family.py agree agreed
```

Copy the store first: the export refuses to overwrite an existing
`world.jsonl`, and writing one into the live run directory would be
overwritten by `_finish` anyway.

**Why it matters.** A task premise measured on one recording does not
survive to the next. Measured at day 28 of v6 against the same window of
the old world: the rate at which people name a weekday **halved**, 30% of
turns to 14%, while owner phrases held at 0.86x and matter mentions rose to
1.21x. A task whose rule required a weekday would have shipped with six
rows, under its own floor, and **not one supersession** — its whole
mechanism absent, scoring a frontier model 1.000 for taking the first
answer because there was never a second one.

That is not corpus growth diluting a proportion, which
`task-viability.md` already knew about. The engine changed, so the firm
changed how it writes. **A rule measured on a world recorded by a
different engine is a rule measured on a different firm.**

## How long it takes, measured rather than guessed

At day 37 the store had been open 9.0 hours: **14.7 minutes per recorded
working day**, steady across the run with no degradation. That puts the
remaining 93 days at roughly **23 hours**, not the "about 17" this note
previously implied — an estimate made early, from a shorter sample, and
repeated without being re-derived.

Two things follow. The recording spans more than a full day of wall clock,
so whoever picks it up will not be whoever started it, which is the reason
this file exists. And the pace is worth re-deriving rather than trusting:
divide the store's mtime minus its birth time by the day count.

## How you know it finished

The supervisor accepts only when **both** the telemetry count and the
exported world hold 130 workdays, and the segment exited zero:

```bash
grep -c '"kind":"day"' out/merrick/epoch/telemetry.jsonl   # 130
grep -c '"sim.day.ended"' out/merrick/epoch/world.jsonl    # 130
```

`world.jsonl` does not exist until a segment finishes — the store is the
source of truth and the log is exported by `_finish`. If the run is killed
permanently, `export_jsonl(store, path)` rebuilds it from `run.db`; nothing
is lost.

## The five tasks, in the order they should be settled

Three of the original eight retired on measured evidence and their solvers
say so in their first line. These five ship:

| task | what to measure first |
|---|---|
| `off-sense-register` | the off-sense share of the admitted word family. The task's own gate wants 60%; an audit found no family in this corpus clears it. If none does, the difficulty is coverage rather than rule, and coverage does not survive bounding. |
| `deadline-week-promise-clock` | the form table narrows from seven to **five** — `end of month` and `by date` are both zero on v6, and the build now refuses a dead category outright. Ranked on 33 days, the week of 2 Feb gives ~26 rows over 60 messages exercising 5 forms; re-rank on the finished record, because the ranking is what picks the window. All seven excluded wordings occur zero times, so the brief must say each is moot rather than implying a reader meets one. |
| `live-commitment-register` | **new, and the only task on the transcripts.** Its rule was already measured dead once: weekday-only deadlines collapsed to six rows on v6, and it now admits the relative forms the corpus writes (243 turns of `end of week`/`EOD`/`COB`/`tomorrow` against 83 weekdays). Re-measure the admitted forms, the window (30 days was 43,779 words, under the 60,000 ceiling), and the supersession share — `measure_transcripts.py` refuses under 15%. Its key is `(matter, owner, day)` on purpose: a matter-keyed register scores a first-answer reader 0.805 and this one 0.687. |
| `prebill-narrative-screen` | keep it bounded — 2.1% over ~23,000 entries is a needle hunt otherwise. **The 60% bar is settled and it was aimed the wrong way.** The row key is (matter, timekeeper), so a misadmitted entry lands inside an otherwise-correct pair and moves `hours` and `fees_dollars` — and the tolerance on hours is forty seconds, so essentially any error fails two of three graded fields. Scoring amplifies admission error here. Take the best family the notes offer (~50%), state the measured share, and read the first sweep for scores too **low**, not too high. |
| `no-op-revision-register` | row count at the intended window; the brief plans for more rows than the measured rate produces. |
| `unanswered-question-register` | the window must close **at least three working days before the record's last day**, or it grades the edge. |

`datasets/merrick/measure_windows.py` sweeps each shipped solver over
candidate windows and prints reader load against row count. It drives the
real solvers, so it cannot drift from the tasks.

## The order that matters

0. **Step 0 above, at day ~25.** Not optional — it is the only step that
   can still change what the tasks *are* rather than whether they pass.
1. **Build.** `datasets/merrick/build_tasks.py`. Eight gates now refuse
   things that used to pass silently — an empty answer key, a world whose
   calendar mixes time units, a task whose grading module would not import,
   a second derivation that disagrees. Read what it refuses; each message
   says what to do.
2. **Re-verify the harness before spending a sweep.** This is task #6 and it
   was reopened for a reason: it was last verified before three
   harness-critical defects were found. Run one trial, confirm the criteria
   load inside the container and a reference answer scores 1.0.
3. **Then rollouts**, k=9, three tiers. `scripts/rollout.py` now refuses a
   task that was never built rather than spending every trial on zeros.
4. **Classify every miss** before recording a number. Only M ships.

## What is known and unfixed

`docs/fidelity/post-freeze-fixes.md` holds five engine defects found during
the recording, each with its location, its measurement, and how to verify
the fix. They are frozen-side; none blocks the five tasks. The most
consequential is the first: a scheduled start is never checked against the
run's clock, which put 8.1% of calendar events outside the world and caused
96% of its scheduling conflicts.

`docs/fidelity/task-viability.md` records why three tasks retired, and the
one confirmed audit finding that did not reproduce — worth reading before
retiring a fourth on someone else's say-so. Its last section carries the
v6 re-measurement and the reason a verdict does not survive a re-record.

**A retirement note can go stale, and a stale one is worse than none.**
`double-booked-week` was retired because 42.4% of calendar starts were
malformed and the served diary was half-size. That cause is fixed — v6 is
1.3% malformed with the beyond-horizon class gone entirely — so anyone
rechecking the recorded reason finds it false and revives the task. The
real reason holds on both worlds and was never written down: this firm does
not double-book, 2 overlapping pairs in 180 days of the old world and 1 in
30 days of the new. Its `task.toml` now says so.

## The build's refusal thresholds, checked against v6 before the build

Every gate that can refuse a world was calibrated on an earlier one. A
threshold tuned for the old corpus refusing a good new one is a turnaround
spent debugging the gate, so they were checked at day 42 rather than at the
build:

| gate | limit | v1 | v6 |
|---|---|---|---|
| `MAX_DROPPED_SHARE` | 0.03 | 0.0000 (1 entry) | **0.0000 (none)** |
| `MAX_REPEATED_REF` | 3 | 1 | **0** |
| artifact mix, markdown | <= 15% | 3.2% | 1.0% |
| artifact mix, office | >= 70% | 96.8% | 99.0% |
| `slack.dm_share` | 0.15-0.35 | 0.000 **FAIL** | 0.250 |
| `slack.threaded_reply_share` | >= 0.30 | 0.0003 **FAIL** | 0.433 |

Everything passes, and v6 is cleaner than v1 on every one. The two that
refused the old world outright are the two the engine fixes were for, so
the build should not need `--allow-band-absence` — and if it does, do not
reach for the flag, because it prints "do not ship rollout numbers from
this world" for a reason.

One number in that table settles an older question. `.pptx` was 3 of 308
documents (1.0%) and the recorded explanation was that the firm had no seed
deck to imitate. It is 4 of 195 (2.1%) on v6 with no seed deck added: the
cause was `_route_document` never converting its draft, so a persona who
spontaneously decided to build a deck simply could not. The deck rate
doubled when that was fixed.

## What v6 fixed, verified on the running recording

| | old world | v6 |
|---|---|---|
| malformed calendar starts | 532/1255 (42.4%) | 7/539 (1.3%) |
| ...beyond-horizon (June 2080) | 149 | 0 |
| `slack.dm_share` | 0.000 | 0.250 |
| `slack.threaded_reply_share` | 0.0003 | 0.433 |
| engine text in world data | 4.8% of time narratives | 0 |
| document paths nested | 4 of 308 | 238 of 241 |
| redundant RSVPs | 73% | ~2% |

The band gate refused the old world outright on the two slack bands. It
should pass on v6 without `--allow-band-absence`; if it does not, do not
reach for the flag — it prints "do not ship rollout numbers from this
world" for a reason.

## The email fix, piloted — and what the pilot can and cannot show

Run at day 47 of v6, four days into a scratch epoch on the fixed engine
(`b6e7102cd06621f2`), concurrency 8. The run shape is comparable: 664 steps
against v6's 667, 147 wakes against 147, batches 291 against 295 — so
concurrency changed wall time and nothing else.

**What is established.** Reply refusals are gone: `refused-reply` is 0 at
sim day 1.55, where v6 recorded 196 of them in 43 days. That one is not a
statistical claim — with the thread's participants filled in, a reply to a
thread that has another participant *cannot* be refused for naming nobody.
The overall refused share is 4.2% against v6's 38.2%, which is the residue
of new threads naming nobody, as designed.

**What the pilot does NOT establish, and nearly got reported as if it did.**
Day 0 shows email 5 -> 15, chat 9 -> 19, documents 10 -> 16 and
`calendar.response` 105 -> 64. The email fix cannot touch RSVPs, and total
events are the same (667 against 664) — so this is not the fix adding work,
it is **trajectory divergence**. Same seed, but the moment one action
resolves differently the two worlds are different samples of a stochastic
process, and every later count is a comparison of two draws rather than a
controlled A/B.

So: quote the refusal numbers, which are mechanical. Do not quote the
volume ratios as the fix's effect.

**The controlled figure does not need a second recording.** It is countable
from v6's own refusal log, because every refusal the fix structurally
cannot make is a message that would have existed. Over 50 recorded days:

    emails sent                                545
    replies refused for naming nobody          216
      of which the fix recovers                201
      blocked anyway by the 12-message cap      15
      thread had no other participant            0

    mail the fixed engine would have produced  746   (+36.9%)

That is a **lower bound**, and deliberately so: a recovered reply draws
further replies, and those second-order messages are not counted. It also
does not need an A/B, because it is not a comparison of two samples — it
is a count of refusals against a rule that can no longer refuse them.

**Thread length is clear.** Reply-all could have pushed threads into the
twelve-message cap; longest is 4, median 3.

## Before the NEXT recording: what the pilot leaves open

The reply-addressing fix is proven by five mutations and has never run in
a real recording. Everything below about its effect is arithmetic on the
old world, not observation of a new one, and this tree's rule is that an
unpiloted change is how a seventeen-hour run gets burned.

Two days at low concurrency, into a scratch epoch, then:

```bash
uv run python -c "import sqlite3, json; \
  c=sqlite3.connect('file:<pilot>/run.db?mode=ro',uri=True); \
  sent=sum('\"email.message\"' in p for (p,) in c.execute('select payload from events')); \
  ref=sum('at least one recipient' in (json.loads(p).get('guidance') or '') \
          for (p,) in c.execute('select payload from events') if '\"sim.gm.note\"' in p); \
  print(sent, ref, ref/(sent+ref) if sent+ref else 0)"
```

Expect the refused share to fall from **38.2%** toward the share that is
genuinely a new thread naming nobody — about a third of the old refusals,
so roughly **12%**. If it does not move, the personas are omitting
recipients on new threads rather than replies and the fix addresses the
smaller half.

Also check that reply-all has not made threads balloon: the referee caps a
thread at twelve messages, and a fill that adds recipients who then reply
could push more threads into that cap. Compare thread-length distribution
against this world's.

## The email defect: measured here, fixed after this world was recorded

> **FIXED in `36984fc`, after v6 had already recorded 44 days.** The
> section below is what was measured on v6 and why it was not restarted
> for it. Any world recorded on the current engine should show the 38%
> back; pilot it first, per the section above.

**38.2% of every attempted email never sends.** Measured at day 43 of v6:
469 emails delivered against 290 refused, all for the same reason — the
draft named no recipient — across 27 distinct senders. It is half of every
rejection in the run (290 of 577), and rejections consume 9.0% of all
turns.

**Two thirds of those are replies.** Of 292 refusals, 196 carry a
`thread_ref` and 92 do not. On a reply the recipients are sitting in the
thread being replied to, so the engine is asking the model to restate
something it already has in front of it and refusing the turn when it does
not. That is the same mistake the calendar had before `CalendarScheduleSpec`
was reshaped: **do not ask a model for something derivable — derive it.**

The design is not careless and the comment on `EmailDraft.to` says why it
is as it is:

> No min_length: a model that returns an empty recipient list should meet
> the GM's instructive rejection like any other malformed intent, not fail
> schema parsing and take the run down with it.

That reasoning is right about robustness. What was never measured is the
yield: crash-safety was bought at 38% of the firm's mail. Both can be had —
the referee should *fill* a reply's recipients from the thread and refuse
only a new thread that names nobody.

**Not fixed here, on purpose.** It needs an engine change, the engine is
frozen for the run, and v6 was already restarted four times. The mail that
does send is correct; there is simply less of it — 11/day against the old
world's 15/day, which is low for a twenty-one-person firm but not
implausible for one that talks in chat and meetings. This is a volume
defect, not a correctness one, and it is the first thing to fix in the
window before the next recording.

Two smaller ones from the same measurement, in the same window:
`that update changes nothing and carries no note` is 87 refusals, and the
workbook-form rejection is 15.

### A false positive worth keeping in the record

The day-43 monitor reported a vocabulary leak. It was not one. Fionnuala
Doherty wrote "bounced twice for missing/malformed recipient" into her own
reflection, and **no guidance string in the entire run contains the word
`malformed`** — checked, zero. She was paraphrasing "an email needs at
least one recipient; name them by full name", which is a clean workplace
sentence, and "a malformed recipient" is ordinary email vocabulary. An
email the system refused to send is, from the sender's side, an email that
did not go; narrating it as a bounce is a fair reading.

Keep the detector broad anyway. `malformed` was the tell that found the
original defect, and one examined false positive in 43 days is a cheap
price for that.

## The second-largest refusal, and why it is not urgent

After the email fix, the largest remaining refusal is `that update changes
nothing and carries no note` — 97 over 51 recorded days, 1.3% of all
turns. It loops: 19 (person, ticket) pairs account for all of them, and
**12 pairs were refused more than twice**, worst `ulrich-bergmann` on
`tkt-000024` **nineteen times**. The persona observes the rejection and
tries again.

**It is waste, not data loss, and that distinction decides the priority.**
A refused reply destroyed a message that should have existed — 201 of them,
distorting what the firm looked like. A refused no-op ticket update
destroys nothing: there was nothing to record. The world is not wrong, some
turns were simply spent on nothing.

The guidance is already actionable — "say what moved, or leave a comment
saying why nothing did" — and the persona does not take either branch. So
the repair is not better wording. The candidates, for the window before the
next recording:

* let the referee treat a no-change, no-comment update as an **idle**: no
  event, no rejection, no memory. Nothing is lost, because nothing was
  going to be recorded, and the loop stops because there is no feedback to
  react to. This is the smallest change and probably the right one.
* or stop offering `update_ticket` when the persona has nothing to change,
  which is action selection and a larger job.

Do **not** have the referee invent a comment. That is fabricating world
data to satisfy a gate, which is the defect this tree has spent the most
effort removing.
