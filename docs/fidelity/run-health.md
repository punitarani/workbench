# Can this recording finish? Checked at day 23 of 130

A run measured in hours fails for boring reasons, and the expensive ones
fail late. These are the exhaustion risks, projected from 23 recorded days
rather than assumed.

| axis | at day 23 | projected at 130 | headroom |
|---|---|---|---|
| world log | 20 MB, 15,662 events | ~115 MB, ~88,500 events | ample |
| cassette | 252 MB | ~1.4 GB | 70 GiB free |
| LM calls | 8,108 network | ~46,700 | cap is 2,000,000 |
| tokens | 41.1M | ~232M | no cap |
| pace | ~600 steps/day | stable across the last 8 days | — |

The call budget deserves a note: it counts **network** calls, and it is
per-process, so every resume starts it again. Two million was never going
to bind. Worth checking anyway — the engine raises on budget exhaustion
rather than degrading, by design, so a cap set carelessly would kill the run
near the end rather than warn early.

## Two rejection numbers that are not the same number

Telemetry reports **405 rejections over 14,407 events, 2.81%**, which sits
alarmingly close to the 3% limit in the attempted-work gate. They are
different measurements and confusing them would be an easy way to panic, or
worse, to relax a gate that is not failing.

*Referee rejections* are the designed loop: a persona proposes an intent the
referee cannot ground, gets a reason back, and works forward. The work is
not lost — it is redirected. Around 3–5% a day is healthy traffic.

*Dropped entries* are what the gate measures: work a persona attempted that
was silently discarded, which is invisible loss and reads as a model that
never tried. Measured across 410 GM notes: **0 dropped entries, 0 unknown
references.** The gate is at zero, not at 2.81%.

The general shape is worth remembering. A rate near a threshold is only
worrying if it is *that* threshold's rate. Two plausible numerators over the
same denominator will happily produce a number that looks like the metric
you care about.

## The calendar server, verified at the protocol rather than the file

Enabling a tool that was previously absent is not obviously safe: before the
fix the wrapper did not exist and the server never spawned, and the tasks
ran anyway. Now it spawns, so a server that crashes on start would be a
regression introduced by the repair.

Driven exactly as the installed wrapper does — `python -m tools.serve
calendar --db calendar.db`, speaking JSON-RPC over stdio:

```
initialize  -> workbench-calendar
tools/list  -> create_event, delete_event, get_event, list_calendars,
               list_events, respond_to_event, search_events, suggest_time,
               update_event          (9, matching the official surface)
list_events -> real rows, America/New_York, stderr clean
```

The quarantine holds where it matters, which is the surface an agent
queries rather than the table underneath it. Asked for everything between
2020 and 2099: **250 events, all in 2026, none outside.** 250 is the page
size the official API also caps at, with `pageToken` to continue — parity,
not a ceiling.

The first row is worth noting on its own: it starts at
`2026-01-05T08:45:00-05:00`. That is the `31500` event — the one the first,
magnitude-based version of the unit rule would have deleted as a "wall-clock
time that lost its date", and the causal rule correctly keeps. The
difference between the two rules is visible in the served data.

## "resuming at 0/130" is a stale line, not a stuck counter

Every monitor event carries `[supervise] resuming at 0/130 workdays` while the
world is demonstrably on day 25. That reads like a progress counter wedged at
zero, which would be serious: the supervisor spends patience when a resume
advances nothing and stops after three, so a counter stuck at 0 would kill a
healthy run.

It is not stuck. Checked directly:

```
$ grep -c '"kind": *"day"' out/merrick/epoch/telemetry.jsonl
25
```

The supervisor prints that line **once, before invoking the runner**, and the
single `resume` it started has been running for hours without crashing. There
has been no second iteration, so there is no second line. The monitor is
showing the most recent thing the supervisor said, which is also the first.

Worth writing down because the failure it resembles and the health it actually
indicates look identical from outside. The distinguishing check is whether the
counter *reads* zero now, not whether the log *says* zero.

Two related facts, confirmed while looking:

**`world.jsonl` does not exist mid-run.** The store is the source of truth and
the log is exported by `_finish` when a segment completes. Nothing is at risk —
`export_jsonl(store, path)` can rebuild it from `run.db` — but materialization,
the build, and the supervisor's acceptance test all read the exported log, so
none of them can run until a segment ends.

**All four office formats are supported.** `artifacts/render` has
`_render_docx`, `_render_xlsx`, `_render_pptx` and `_render_pdf`. The bundle on
disk holds only .docx and .xlsx because it was built when the world had 30
documents and no deck; the world now records a .pptx and two .pdf. Absence in
a stale bundle is not absence of capability — check the mtime before drawing
the conclusion.
