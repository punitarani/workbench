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
   deterministically from the committed cassette forever after.

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

For scale: the engine records live at roughly 0.1 steps/s against a
hosted model, so six months of *live* simulation would cost weeks of
wall time. The hybrid split — deterministic chronicle for the past,
engine for the day that matters — produces the same world shape in about
a second plus one recorded day.

### Live day (engine, hybrid continuation)

<!-- FILL: record metrics -->

### Windowed engine benchmark

<!-- FILL: bench.json -->

### Determinism and resume

<!-- FILL: acceptance results -->

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
