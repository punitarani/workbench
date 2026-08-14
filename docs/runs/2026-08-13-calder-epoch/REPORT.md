# Calder epoch — the LLM-first engine, end to end

The engine pivot in one sentence: the simulation is now **primarily
LLM-driven** — every employee is a generative agent with a memory
stream, retrieval, a morning plan, end-of-day reflection, and real
meetings; the outside world is LLM-driven client actors stirred by a
seeded seasonal director; and every byte of it replays deterministically
from content-keyed cassettes.

## What an epoch day is

Each workday, minted at `sim.day.started` by the deterministic day
chain:

1. **Planning cohort** (deep tier): all 16 personas lay out the day in
   time blocks anchored to their real calendars; the GM clamps and
   numbers revisions. Decide prompts carry the plan with the current
   block marked.
2. **Wake cohorts** on a 30-minute grid with seeded phases — co-landing
   wakes batch in the windowed engine (max batch = full cast).
3. **Meetings**: calendar events with 2+ simulated attendees convene;
   each turn is one persona speaking with its own private knowledge; the
   transcript is a validated world event. Attendee wakes suppress
   mid-meeting.
4. **Client cues**: the season director (accounting calendar: month-end,
   filing season, estimate weeks, January 1099s) stirs client actors on
   a seeded quasi-Poisson schedule, day-capped; their models author the
   inbound mail. Replies ride the standard grants and depth caps.
5. **Reflection cohort** (deep tier) on the last tick: daily summaries
   with model-scored importance bullets, weekly rollups every fifth
   workday — the consolidation that keeps prompts O(1) over months.
6. Rejections route back to their actor as importance-10 memories.

## Architecture guarantees carried over the pivot

- **Byte determinism**: replay from the cassette is byte-identical at
  any window size and across a kill at any committed step (roll-forward
  resume restores LM counters, memory facts, and cast growth from the
  log + durable meta). Proven by `test_calder_epoch_acceptance.py`.
- **Groundedness**: agents cannot hallucinate world state — memories
  fold from validated events, reflections' refs are GM-filtered, every
  artifact passes reference resolution.
- **Loud failure**: cassette misses, budget stops, and transport
  exhaustion always raise; only deterministic parse failures degrade
  (to minimal notes/plans/"(listens)" turns), so replays cannot diverge
  from recordings.

## Models

| Tier | Model | Used for |
|---|---|---|
| fast | `deepseek/deepseek-v4-flash-0731` (deepinfra chain) | decides, drafts, client actors |
| deep | `anthropic/claude-haiku-4.5` (amazon-bedrock) | PlanDay, Reflect, MeetingTurn |

(The planned `deepseek-v4-pro` deep tier is blocked by this account's
OpenRouter data policy; the first recording attempt caught this because
transport failures now fail loud instead of masquerading as fallbacks.)

## Two-day acceptance recording (the committed dataset)

Recorded after the review fixes (12 seed engagements at genesis,
ref-type guidance in decide, a 12-message thread cap with instructive
rejections):

| Metric | Value |
|---|---|
| Steps / events | 467 / 520 (to quiescence) |
| LM calls | 390 (616k prompt / 71k completion tokens across both tiers) |
| Max batch | **16 — the full persona cohort acts concurrently** (the old engine peaked at 2) |
| Per-day shape | 16 plans, ~120 wakes, 16 reflections, a held huddle, seeded cues, real engagement time-logging |
| Audit | **all gates green** — 11% rejection rate, max thread exactly 12, plans/reflections every day, 8 cues, distinct mail |
| Cassette | committed to the repo (reviewed: prompts/completions only, no credentials) |

Replay proof (`tests/workplaces/test_calder_epoch_acceptance.py`,
running in CI on every push now that the cassette is committed): the
recorded run reproduces **byte-identically** at window=1, window=32,
and killed-at-arbitrary-step-73 then roll-forward resumed.

Content samples from an earlier same-engine record (verbatim):

- **Client inbound** (Dana Whitfield, Kestrel controller, from a seeded
  cue): *"We're prepping the close for the board, and the margin figure
  they're asking about is pulling more than expected against the prior
  quarter. I need your eyes on the numbers before Thursday…"*
- **A partner's morning plan** (Rosalind): 08:00 admin & policy review →
  09:00 tax group huddle → 10:00 client outreach → 11:00 close checklist
  review — anchored to the real calendar event.
- **A daily reflection** (Rosalind, scored bullets): *"!8 Onboarded core
  operational policies and templates… !7 PBC request template scope
  clarified with team"* with the open loop *"Sub-entity PBC gaps —
  monitor during reviews."*
- **The huddle transcript** (5 turns): Victor runs the queue, Desmond
  reports returns in review with a messy basis calculation, Lucia
  reports the Stonebridge K-1s — each speaking from their own staffing
  and knowledge.

Review findings fixed before committing the dataset: the epoch world
initially had no engagements, so time-logging personas invented ticket
refs (22% rejections → 11% after seeding the twelve engagements and
spelling out ref kinds); wake-driven email ping-pong produced a
24-message thread (now capped at 12 with feedback the persona
remembers).

## One-week flagship

Five simulated workdays, full cast (16 personas + Maya's machinery + 11
client actors), recorded live at window=32:

| Metric | Value |
|---|---|
| Steps / events | 1,195 / 1,248 |
| LM calls | 1,002 (1.68M prompt / 186k completion tokens) |
| Wall | **28.7 min (~5.7 min per simulated day)** |
| Per-day | ~240 steps, ~200 calls, plans + reflections every day, 23 cues over the week |
| Audit | all gates green — 13% grounding failures (halved by reaction leniency), 8 thread-cap brakes, max thread 12, 137/138 distinct mail bodies |
| Determinism | same engine, same cassette contract as the committed 2-day dataset |

Rejections held roughly flat day-over-day (5→6/day after the fixes)
instead of climbing — the failure-feedback loop plus graceful ref
interpretation is doing its job.

## The six-month epoch (one command)

```bash
uv run --env-file .env python datasets/calder/run_epoch.py start \
  --days 194 --mode record --out out/calder/epoch-6mo --window 32
```

Resumable at any point (`run_epoch.py resume`), observable from another
terminal (`status`), audited afterward (`audit`).

Extrapolating from the measured flagship week (~200 calls, ~5.7 min,
~340k prompt tokens per day): the 128-workday epoch lands around
**26k LM calls, ~44M prompt tokens, and ~12 hours of wall clock** in
resumable weekly segments — an overnight job, interruptible at any
committed step.
