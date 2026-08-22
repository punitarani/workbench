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
