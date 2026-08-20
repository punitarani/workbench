# What to do when the recording finishes

Written at day 30 of 130 with everything corpus-independent complete, so the
work resumes from the blocking condition rather than from whatever was most
recently on someone's mind.

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
| `deadline-week-promise-clock` | the form table narrows from seven to the four the firm writes. `EOD` is ~62% of hits and needs no arithmetic, so say in the brief whether the clock is the point. |
| `prebill-narrative-screen` | keep it bounded — 2.1% over ~23,000 entries is a needle hunt otherwise. **The 60% bar is settled and it was aimed the wrong way.** The row key is (matter, timekeeper), so a misadmitted entry lands inside an otherwise-correct pair and moves `hours` and `fees_dollars` — and the tolerance on hours is forty seconds, so essentially any error fails two of three graded fields. Scoring amplifies admission error here. Take the best family the notes offer (~50%), state the measured share, and read the first sweep for scores too **low**, not too high. |
| `no-op-revision-register` | row count at the intended window; the brief plans for more rows than the measured rate produces. |
| `unanswered-question-register` | the window must close **at least three working days before the record's last day**, or it grades the edge. |

`datasets/merrick/measure_windows.py` sweeps each shipped solver over
candidate windows and prints reader load against row count. It drives the
real solvers, so it cannot drift from the tasks.

## The order that matters

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
retiring a fourth on someone else's say-so.
