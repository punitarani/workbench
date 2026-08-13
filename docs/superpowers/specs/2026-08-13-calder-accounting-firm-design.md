# Calder & Finch, CPAs — a six-month medium-size accounting firm

**Goal.** Generate a medium-size accounting firm (10–25 people) with at
least six months of simulated history, materialized into a tool-backed
environment, and capture time/efficiency metrics that demonstrate the
engine-revamp improvements. Everything must build offline and
deterministically except the one engine-simulated live day, which records
a committed cassette so replay is deterministic forever after.

*Authored autonomously under the user's standing directive ("generate,
verify end-to-end, then push"); the interactive design-approval gate was
skipped for that reason and the decisions are recorded here instead.*

## Shape of the deliverable

Two proven generation modes exist and this build uses both, the way the
Hartwell four-month history did:

1. **Chronicle** (offline, byte-deterministic): genesis + procedural
   background traffic + deterministic directed arcs for all 194 calendar
   days. No LM calls anywhere — arc prose is template-authored, like
   `ProceduralVoice`, not `ContentStore`-authored. `--check` builds twice
   and compares bytes.
2. **Engine** (live once, then replay): one hybrid-continuation day after
   the chronicle window, simulated by 17 LM personas through the revamped
   engine (`compile_workplace(..., time_offset=..., starting_minter=
   minter_from_events(history), include_genesis=False)` +
   `run_compiled(..., history=...)`), recorded to a committed cassette.
   This is the surface where the revamp's D/E/F/G phases all execute on
   real scale.

## The firm

**Calder & Finch, CPAs** (`workplace_id="calder"`), Portland OR,
`America/Los_Angeles`. Seventeen internal people at full strength:

- 2 founding partners (managing + tax), 1 audit principal
- tax manager, audit manager (called "senior manager, assurance")
- 3 senior accountants, 4 staff accountants (one of whom **joins mid-window**)
- client-accounting lead (bookkeeping), payroll specialist
- office/billing manager, admin coordinator, IT administrator

Thirteen are timekeepers with realistic rates ($95–$425/hr) and billable
targets. Ten client organizations (manufacturer, restaurant group, dental
clinic, nonprofit, property management, construction, SaaS startup,
retail, brewery, physical-therapy group) with named external contacts.
Twelve engagements (= tickets): monthly closes, tax returns, the
nonprofit audit, payroll, an advisory project.

## Window and rhythm

`CalendarWindow("2026-01-05" → "2026-07-17")` — 194 days, just over six
months, chosen to contain a full accounting-calendar arc:

- January: year-end close, 1099s, engagement letters
- February–April 15: tax season (directed crunch traffic + overtime
  entries layered by the arcs; procedural intensity stays ≤ 1.0)
- April 15: deadline day; extensions filed
- May–June: post-season closes, the audit fieldwork, June 15 estimates
- July: quiet run-out to the live day

`day_profile` mirrors Hartwell: federal holidays at reduced intensity,
weekend jitter, workdays at 1.0.

## Directed arcs (all deterministic templates)

1. **Month-end close** (Jan–Jun): per close-client, a document-request
   email around the 25th, close-work traffic in the first week of the
   following month, and a close-complete summary email.
2. **Tax season**: engagement-letter emails in January; PBC request/
   chase threads per tax client; directed overtime `work.time.logged`
   entries Mar 1–Apr 15 for tax staff; deadline-day flurry; extension
   confirmations for two clients.
3. **New hire**: staff accountant Maya Okonjo's `person.record` lands
   mid-log on 2026-03-02 with a welcome email and standup mention; the
   procedural cast swaps to include her from that date (Hartwell's
   `_without_matter` pattern, in reverse).
4. **Quarterly estimates**: reminder emails ahead of Jan 15, Apr 15,
   Jun 15 to estimate-paying clients.
5. **Nonprofit audit**: fieldwork calendar events, a PBC list document
   with revisions, status emails Feb–May.

## File artifacts (Phase F on display)

Genesis seed documents include structured content: the standard rate
sheet and the client master list as `content_format="spreadsheet"`
(canonical `SpreadsheetContent` JSON), the monthly-close checklist as
`content_format="formatted"`. Materialize renders real `.xlsx`/`.docx`
into the agent workspace; PDF renders when `soffice` is present, else the
skip is recorded.

## The live day (2026-07-20, Monday)

`spec.py` declares the engine-day `WorkplaceSpec`: full roster with
personas (identity, style, knowledge), a day script of exogenous client
emails (a missing-receipts panic, a notice from a state agency, an
estimate question), seed surfaces omitted (`include_genesis=False` — the
world already exists). A few personas carry `extra_verbs`
(`log_time`, `react_chat`, `schedule_meeting`) — safe here because this
cassette is recorded fresh. Recording runs at `window=8` on
`deepseek/deepseek-v4-flash-0731`; the cassette is committed and the
acceptance test replays it at W=1 and W=8 and byte-compares, plus an
interrupt/resume split.

## Metrics (the point of the exercise)

Captured by the build driver and the live-day runner, reported in
`docs/runs/2026-08-13-calder-six-month/REPORT.md`:

- Chronicle: wall time, total events, bytes, events/sec, validate time,
  determinism-check time, per-month tag counts.
- Materialize: wall time, document files (incl. rendered office files),
  bundle size.
- Live day: wall time at W=8 (live) vs W=1 (live, separate scratch
  cassette — window invariance means both runs issue the same request
  set, so the comparison is apples-to-apples), steps, LM calls, token
  usage, seconds/step, speedup ratio; `run.db` size and snapshot count
  (D0 slimming at work).
- Fabric audit (realism gates, adapted from Hartwell's): repetition
  bounds, distinct-body ratios, billable hours/day inside a plausible
  band, weekend/holiday share, per-engagement hour spread.

## What is intentionally not built

- No Harbor tasks, oracles, or evidence ledgers — this deliverable is
  the simulation + environment, not a benchmark suite.
- No LM-authored storyline prose (`ContentStore`): template prose keeps
  the whole history reproducible with zero network and zero cache.
- No grant matrix / access scoping (deferred repo-wide).

## Verification gates

Structural tests for genesis/arcs/build (offline, fast, in CI); full
`uv run pytest` + `uv run ruff check .` green; the 6-month build passes
`validate_events`, `check_coherence`, and the fabric audit; the live-day
cassette replays byte-identically at W∈{1,8}; push only after all gates
pass.
