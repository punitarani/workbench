---
name: running-recorded-simulations
description: Use when running, supervising, resuming, or babysitting a long generative simulation or recording that takes hours to days - covers supervisor design, the resume-not-restart rule, what may and may not change while a run is live, and accepting on the artifact instead of the progress log. Reach for this whenever a run is measured in days of simulated time or hours of wall time, whenever you are tempted to restart something that died, and whenever you find a defect while a recording is still in flight.
---

# Keeping a long run alive without corrupting it

A multi-day recording is tens of thousands of model calls over hours of
wall time. Over that long it does not fail for interesting reasons. It
fails because a socket dropped, a provider returned a 5xx after its own
retries, or the machine slept.

Two things go wrong around runs like this, and both are worse than the
crash that started them: **restarting what should have resumed**, and
**changing the thing being recorded while it records**.

## Resume, never restart

The single most expensive mistake available here is a supervisor that
issues a fresh start after every failure. One such loop reset a recording
to day zero **nine times**. Each attempt died in the first ten minutes,
the supervisor treated it as a fresh failure, and the run never passed
day one. It cannot converge, and it looks like progress the whole time
because something is always running.

Branch on whether a run **exists**, not on whether it has produced
progress:

```
if no store exists:  start
else:                resume
```

The store is created before the first step completes, and `start` refuses
to overwrite one. So the most likely failure — a crash before the first
checkpoint — leaves a store that `start` will reject and `resume` will
happily continue. A supervisor that branches on progress issues `start`,
gets refused, and concludes the run is unrecoverable while the working
path was never tried.

## Spend patience on stalls, not on failures

Retrying forever turns a loud failure into a quiet one. Retrying three
times because the network is flaky is correct. The distinction is
progress, not attempts:

- progress since the last attempt → reset the patience counter
- no progress → spend one
- three consecutive attempts that advance nothing → **stop, and be loud**

A run that dies three times without completing one more unit of work is
broken, not unlucky. Print the tail of its log to stderr and exit
non-zero so a human sees it.

## Accept on the artifact, never on the progress log

These are two different files written at two different times. A progress
log gains a row as each unit completes; the durable artifact is usually
written once per segment, at the end. A kill between the two leaves the
progress log claiming work the artifact does not contain.

Reproduced: eight rows in the progress log, seven in the artifact, and
the supervisor printed "done" and exited zero. Nothing downstream checks
span, so the truncated world would simply have become the graded one.

Accept only when **both** the artifact holds the target and the process
exited zero. Capturing an exit status and then using it only in a log
line is the same bug wearing a disguise.

## Shell traps that make a supervisor lie

These are worth naming because each one produced a wrong number rather
than an error.

**`grep -c` prints `0` and exits `1`** when nothing matches. Written as
`count=$(grep -c ... || echo 0)` both fire, the variable becomes `"0\n0"`,
and every integer comparison downstream errors and evaluates false —
including the stall check, which then spends patience a run had earned.

**A pipe hides the exit code.** `cmd | tail -5` returns `tail`'s status,
which is always zero. Capture `$?` from the command itself, or the
supervisor cheerfully reports success for a failed run.

**Derived counts drift from real ones.** If the run skips weekends,
`days * 5 / 7` is not the number of working days — it was off by two over
six months, and the supervisor would have announced a complete world two
units short. Compute the real count from the calendar.

## What may change while a run is live

You will find defects mid-run. Most of them must wait.

Freeze anything that changes **what gets written**: the simulation loop,
the agent prompts, event payload shapes, and anything feeding a
cache/replay key. Changing these mid-run makes the first half of the
record and the second half two different worlds, and nothing will tell
you.

Downstream layers are safe. A projection that reads a finished log and
builds serving state can be rebuilt any time — re-running it reproduces
whatever the log says. So can analysis, gates, and task code.

**Verify the boundary by computing the import closure. Do not try to ask
the running process.** Reading one file's imports understates reach —
imports are transitive and can be routed through a registry — but the
obvious remedy does not work either. CPython opens a source file, compiles
it, and closes it, so `lsof` on the running process shows **no** `.py`
files at all, including the ones it is certainly executing. It reports
nothing for every package, which reads as "not reached" for every package.
A check that always passes is worse than no check, because you act on it.

Walk the imports statically instead, transitively, from the runner:

```bash
python scripts/import_closure.py run.py --src src --check serving_layer analysis
#   core             31 modules
#   simulation       39 modules
#   serving_layer: not reached -- safe to edit
#   analysis: not reached -- safe to edit
```

Anything inside the closure is frozen. Anything outside it is downstream:
it reads a finished log, so rebuilding it later reproduces whatever the log
says, and it can be changed while the run continues.

When you find a frozen-side defect, write it down where the fix will be
made and keep going. A defect recorded is cheaper than a restart, and a
world with a known flaw beats a world that never finishes.

## Sizing the run before committing to it

Concurrency does not help past the width of one tick. If every agent
wakes on the same tick, useful concurrency equals the cast size and
anything beyond it queues. Cast size is close to free; **the tick count
and the slowest agent in each tick are what you actually pay.**

Before committing to a long run, record one unit end to end. A one-day
smoke test costs minutes and has caught pipeline defects that would
otherwise surface after hours of recording.

## The supervisor

`scripts/supervise.sh` implements all of the above — existence-based
branching, progress-based patience, artifact-plus-exit-code acceptance,
and the shell traps handled. It takes the two commands it should run and
the two predicates it should test, so it is not tied to any one runner:

```bash
scripts/supervise.sh \
  --start   "python run.py start --days 180 --out $OUT" \
  --resume  "python run.py resume --out $OUT" \
  --progress "grep -c '\"kind\": *\"day\"' $OUT/telemetry.jsonl" \
  --artifact "grep -c '\"tag\": *\"day.ended\"' $OUT/world.jsonl" \
  --target 130
```

Related: `building-simulated-worlds` for what the run must produce,
`validating-task-premises` for what to measure once it has.
