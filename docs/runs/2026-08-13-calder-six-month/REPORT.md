# Calder & Finch, CPAs — six-month simulation and environment

A medium-size accounting firm (17 people at full strength, ten clients)
with just over six months of simulated history (2026-01-05 → 2026-07-17,
194 calendar days) plus one engine-simulated live day (Monday
2026-07-20), materialized into a tool-backed environment. Everything
except the one recorded live day builds offline and byte-deterministically.

## Architecture

Two generation modes compose, the same split the Hartwell four-month
history proved out — now running on the revamped engine end to end:

1. **Chronicle** (`datasets/calder/build_history.py`): genesis +
   procedural background traffic + five deterministic template-authored
   arcs (month-end closes, filing season with the April 15 crunch,
   quarterly estimates, a mid-window hire, a nonprofit audit). Zero LM
   calls; `--check` builds twice and byte-compares.
2. **Engine live day** (`datasets/calder/run_live_day.py`): the full
   17-persona cast simulated through the revamped engine as a hybrid
   continuation (`compile_workplace(include_genesis=False,
   time_offset=…, starting_minter=minter_from_events(history))`),
   recorded once against `deepseek/deepseek-v4-flash-0731` and replayed
   deterministically from the cassette (kept local, per the repo's
   cassette policy) forever after.

The revamp phases all execute at scale here: multi-day calendar shape
(D), the arrival Maya Lindqvist joining mid-window (E2), `log_time` /
`react_chat` / `schedule_meeting` verbs on eight personas (E1),
structured spreadsheet/formatted artifacts rendered to real `.xlsx` /
`.docx` (F), and the windowed engine + snapshot event-refs carrying a
22,000-event history (G, D0).

## The world

- 16 employees at genesis; staff accountant Maya Lindqvist arrives
  2026-03-02 (`person.record` mid-log, DM created at arrival, cast
  swap). Chat membership is fixed at conversation creation — no
  member-add event exists — so Maya is **channel-silent by
  construction**: she participates through email, DMs, time entries, and
  engagement staffing. This is a documented world-model limitation, not
  an oversight.
- Ten client organizations; twelve engagements (closes, returns, the
  Harbor Light Foundation audit, payroll, advisory, cleanup).
- Seed documents include structured artifacts: the 2026 rate sheet and
  client master list as spreadsheets, the monthly close checklist as a
  formatted document. The close arcs emit 28 spreadsheet reporting
  packages that ride client emails as attachments; the audit arc ships a
  formatted draft-financial-statements deliverable.
- Fabric audit (21 gates, all green): no chat surface repeats one body
  above 5%; 1,238 distinct DM bodies; 1,765 distinct billing narratives
  across 12,730 entries; every entry rated with $2.87M billed over the
  window; 6.60 billable hrs/workday average (4.75–7.86); engagement
  hours spread 19.6×; filing season runs 1.15× the shoulder rate; 4.3%
  of traffic lands on weekends/holidays.

## Metrics

### Chronicle build (offline, deterministic)

| Metric | Value |
|---|---|
| Calendar days | 194 |
| Events | 22,000 |
| World log | 7.6 MB |
| Build wall time | ~0.95 s |
| Events/second | ~23,000 |
| Validate | ~0.10 s |
| Materialize | ~0.41 s (38 document files, 0 skipped renders) |
| Bundle size | 3.6 MB |
| Determinism check (two full builds) | 1.9 s, byte-identical |

For scale: the engine records live at roughly 0.16 steps/s against a
hosted model, so six months of *live* simulation would cost weeks of
wall time. The hybrid split — deterministic chronicle for the past,
engine for the day that matters — produces the same world shape in about
a second plus one recorded day.

### Live day (engine, hybrid continuation)

Recorded once, live, at `window=8`; deterministic replay from the local
cassette ever after (cassettes stay out of git per repo policy — the
acceptance test self-skips without one).

| Metric | Value |
|---|---|
| Steps to quiescence | 264 |
| New events | 264 (92 emails, 10 time entries, 7 ticket comments, 2 tickets created, 3 document revisions, 3 chat messages, 141 wakes) |
| LM calls | 270 (531k prompt tokens, 38k completion) |
| Wall time (live recording) | 1,693.8 s (28.2 min) |
| Cassette | 267 entries, 2.8 MB |
| `run.db` | 12.0 MB carrying the full 22,264-event world |
| Combined log validates | yes |

Day quality: the four planted client emails all drew grounded responses —
Gabriel explained the June inventory movement from his seeded knowledge,
Sylvia answered the state notice by citing the Q1 amendment, Victor
addressed the study-invoice question, and the payroll-services inquiry
produced a tracked ticket. Personas also picked up threads from the
*history* (replying to procedural mail from the previous week), and the
E1 verbs fired repeatedly: ten `work.time.logged` entries with sensible
narratives landed against the correct engagements. The cast strongly
preferred email over chat on this day (92:3) — a plausible Monday-inbox
shape, and a knob future day scripts can pull on.

### Windowed engine benchmark

`datasets/calder/benchmark_windows.py` replays the recorded day with
per-call LM latency modeled at 3.0 s (cassette hits are otherwise
instant, which would measure nothing) and probes admission batch sizes:

| Window | Wall | Batches | Max batch | Multi-step batches | Speedup |
|---|---|---|---|---|---|
| 1 | 815.1 s | — | — | — | 1.00× |
| 8 | 716.0 s | 239 | 2 | 25 | **1.14×** |

Both windows produce byte-identical worlds — the invariance guarantee is
the hard result; the speedup is workload-dependent. This day batches
modestly by design: the single-day compile staggers persona wakes three
minutes apart (the byte-compat wake ladder), so same-effective-time
collisions arise only from response scheduling — 25 real two-step
batches. Denser day scripts, same-time wake cohorts, or the multi-day
scheduler produce more same-time pressure; what the engine guarantees is
that any window size yields the same bytes while concurrent LM calls
shrink the critical path.

A second fully-live sequential recording was deliberately skipped: live
sampling differs run to run, so it would compare two *different* days at
real cost — the modeled replay compares the same day exactly. The real
live figure on record is the window=8 recording above (28.2 min).

### Determinism and resume

`tests/workplaces/test_calder_acceptance.py` (activates when the local
cassette exists) rebuilds the 194-day history from scratch, then replays
the recorded live day three ways and byte-compares the combined
22,264-event logs:

- sequential (`window=1`) — the reference;
- windowed (`window=8`) — **byte-identical**, same step count;
- interrupted at step 50 + resumed — **byte-identical**, steps sum to
  the straight run's 264.

Everything from the first genesis byte to the last live-day event is
reproducible from source + seed + cassette; the only nondeterministic
act in the whole pipeline was the one recorded day, captured once.

## Deviations and limitations

- Maya never posts in channels (above). Her live-day persona can still
  email, DM, log time, and comment tickets.
- The live-day cassette pins provider order (deepinfra → fireworks →
  novita → deepseek) at record time; cassette keys exclude the provider,
  so replay needs no network at all.
- `OpenRouterLM` defaults to an openai-only provider order; the Calder
  runner passes its own chain. The repo default model
  (`openai/gpt-5.6-luna`) is not served for this account's key.
- Season overtime rides as directed entries on top of the procedural
  baseline; a person's absence days and their directed overtime are
  drawn independently, so an "away" fee earner can still show a directed
  entry — read as evening catch-up.
