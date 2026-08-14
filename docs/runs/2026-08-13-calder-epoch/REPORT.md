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

## Two-day acceptance recording

<!-- FILL: metrics -->

## One-week flagship

<!-- FILL: flagship metrics + audit + samples -->

## The six-month epoch (one command)

```bash
uv run --env-file .env python datasets/calder/run_epoch.py start \
  --days 194 --mode record --out out/calder/epoch-6mo --window 32
```

Resumable at any point (`run_epoch.py resume`), observable from another
terminal (`status`), audited afterward (`audit`).

<!-- FILL: extrapolated estimates from flagship -->
