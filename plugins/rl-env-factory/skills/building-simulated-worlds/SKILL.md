---
name: building-simulated-worlds
description: Use when generating a simulated workplace, institution, or multi-agent history that tasks will be graded against - covers determinism, the offstage boundary, coherence gates, artifact realism, and fidelity measurement. Load before writing any world generator.
---

# Building a world worth grading

The world must be *true* before anything cut from it can be *fair*.

## Non-negotiables

- **Determinism is the product.** Every generator takes an explicit seed
  and produces identical bytes for identical input. No wall-clock, no
  unseeded randomness, no dependence on dict or filesystem ordering.
  Without this, no measurement repeats and no defect reproduces.
- **Every ordering on the replay path is explicit.** Gather concurrent
  results in declaration order, never completion order; assign sequence
  numbers at emission, not at enqueue. Concurrency that reorders is
  nondeterminism wearing a performance argument.
- **Split generation by kind.** Structure the institution's own systems
  would produce — rosters, records, cycles, calendars — derives
  deterministically from the seed. Every piece of language or judgment is
  a model call grounded against that structure. **A structural generator
  that starts emitting prose has crossed into authorship**, and prose
  from a structural generator is the same sentence every time.
- **The referee is deterministic: zero model calls.** Whatever turns
  actor intents into world facts resolves each reference against world
  state or rejects the intent, and rejections become feedback the actor
  sees. A referee that improvises cannot be replayed.
- **Loud failure, always.** Cassette misses, budget exhaustion, integrity
  violations, transport errors — all raise. A world that degrades
  silently produces scores that mean nothing and cannot be traced.
- **The offstage boundary is structural, not conventional.** The agent
  reaches the world through materialized data and tool servers over
  projected databases — never through simulation internals, personas,
  hidden state, or reward logic. Enforce it in the type system so it
  cannot be forgotten.

## Gates that belong to the world, not the task

- **Coherence before materialization.** Contradictions block.
  Ambiguities are *reported and keyed around*, never silently graded — a
  record that says two things with no stated precedence cannot be graded,
  because the answer would depend on which statement the agent read
  first. Reported ambiguities are raw material for hard tasks.
- **Derived directories are rebuilt wholesale, never incrementally.** A
  materializer that writes files and never removes them accumulates
  several worlds in one directory. This stays invisible until the first
  task grades those files: **a defect in a surface nothing reads has no
  test that can fail.** The same logic covers docs, generated indexes,
  and any output whose only consumer is a human.
- **Refresh derived truth from the world you actually shipped.** A
  default path pointing at a different build than the bundle silently
  derives a fresh answer key from a stale world.
- **Find what actually serializes before provisioning for parallelism.**
  A generated world's cost is not its total call count, it is the length
  of its critical path. In one engine, actors wake in cohorts and the
  whole cast wakes together, so useful concurrency equals the cast size —
  measured at exactly the internal headcount, with everything provisioned
  above it doing nothing. Two consequences, and the first is easy to get
  backwards: **cast size is nearly free**, because a cohort runs in
  parallel, while **tick count and tail latency are the whole cost**.
  A rate like "calls per minute" hides this; a histogram of concurrent
  work does not.
- **A cohort's wall time is its slowest member.** A model tier used by one
  call in ten still sets the pace for the other nine. Reach for the fast
  tier when buying fidelity — it writes the world — and keep the deep tier
  cheap enough not to dominate the critical path.
- **Coarsening the simulated clock does not buy wall time.** Widening the
  wake interval threefold gave each actor threefold more accumulated
  context per wake, so per-tick work rose and cancelled the tick
  reduction. The work a simulated day contains is a property of the day,
  not of how finely it is sliced.
- **Read what the referee refused, not only what it recorded.** A
  deterministic referee resolves every reference against world state and
  rejects what it cannot resolve — that is exactly right, and it means a
  world can be *structurally incomplete* while every component behaves
  correctly. The actors reach for something the world does not offer, the
  referee refuses, and the record simply has less in it than the day did.
  Measured: 16.8% of one firm's attempted timekeeping vanished because the
  people had administrative and internal work to book and no code to book
  it against, so they invented plausible ones and every rejection was
  correct.

  Nothing else catches this. **Coherence checks look for a fact carrying
  two values; they cannot see a fact that was never recorded.** The
  materializer writes what exists, and any figure computed over the
  survivors is perfectly self-consistent and answers a question about an
  institution that does not exist. Gate the *loss rate* out of the
  referee's own rejection notes, and write the gate's message so it blames
  the world rather than the referee — otherwise the next reader fixes it
  by making the referee permissive, which trades a visible gap for an
  invisible one.
- **A bound applied in declaration order encodes a priority nobody
  chose.** Any list an actor is shown gets capped so it does not flood the
  prompt, and the cap almost always keeps the first N. But what is
  declared last is usually the *shared* material — the institution-wide
  codes, the defaults, the things belonging to nobody in particular — and
  those are exactly what every actor needs. Measured: standing matter
  codes fell outside the cap for the whole cast, people invented
  references for work they genuinely had to record, the referee correctly
  refused, and 20.7% of attempted timekeeping vanished.

  The trap has a second half worth naming. The obvious fix — *add the
  missing codes* — made it **worse**, 16.8% to 20.7%, because six more
  entries pushed the shared ones further past the cap. **Fixing the
  symptom a rejection names, without measuring the mechanism underneath,
  can move the number the wrong way.** Reserve the shared slots
  explicitly, and make the reservation a no-op below the cap so every
  existing recording stays byte-identical in content *and order*.
- **Set thresholds between two measured worlds** — a known-bad and a
  known-good — rather than at a round number. A band picked by intuition
  either never fires or fires constantly, and either way stops being
  read.

## Never ask a model for arithmetic, then record the answer as world data

Three defects in one world turned out to be one mistake repeated: an
intent asked a language model for something models are unreliable at, got
unreliable output, and wrote it into the record as a property of the
firm. Each was then *measured* as a data defect and worked around.

The worst was a calendar. The intent took `start` and `end` as raw
seconds on the simulation clock. Seven persona-scheduled meetings in one
recorded day:

    1717609200   a real-world Unix timestamp — reads as June 2080
          1717   00:28
          1200   00:20
       1400400   05:00
       1300000   01:06
         37800   10:30   a meeting
         33300   09:15   a meeting

Two of seven. Across six months, 42.4% of calendar starts were not
seconds-from-epoch at all; half the diary was quarantined before serving
and a whole task was retired for want of a calendar to read. None of that
is a model failure — a person books a meeting by day and wall clock, and
the arithmetic belongs to the referee. The intent now takes a bounded
`day_offset` and two `HH:MM` clocks, and the shape that produced June
2080 has no field it fits in.

The same shape twice more in the same world: internal ids written into
prose because the persona was shown ids and had to be trusted not to use
them, and reply threading pointed at whatever message the persona was
last shown rather than at the thread root.

**The test.** For every field an intent asks a persona to fill, ask what
it would take to get it right. If the answer involves arithmetic on an
epoch, resolving an identifier, or holding a structure the prompt never
showed, the field is in the wrong place. Move the work to the referee and
leave the persona the part a person actually does.

Corollary worth its own line: **a validator that only catches the
causally impossible is not enough here.** The one guarding those calendar
starts refused negatives, dates before the run, and dates past any
horizon — so the 2080 timestamp was caught and the 01:06 meeting was
served. Bad output that lands inside the plausible range is exactly what
this kind of defect produces.

## Realism of the served surface

**Vendor parity constrains realism.** Adding *content* a real product
would serve is a gain. Adding *tools* it would not is a loss wearing a
gain's clothes: an agent trained against an invented tool learns a call
that fails in the real product. When a surface cannot host your content,
put the content where the real product would.

**Artifacts must be the file types the institution actually exchanges.**
A world whose every document is markdown is not the world it claims to
model, and it quietly removes a whole class of work — opening a workbook,
reading a deck, extracting a table from a PDF. Declare the real content
format at emission (formatted document, slide deck, workbook, print
form), not at render time, because the renderer can only produce what the
event asked for. Then gate the resulting distribution: assert the share
of each format directly, or the world drifts back to plain text one
convenient default at a time.

Formats also need to be *load-bearing*. A workbook whose only content is
one flat table is markdown with extra steps; give it the multiple sheets,
formulas, and cross-references the real artifact would have.

## Smoke the whole pipeline on one day before recording many

Generating a long history is the most expensive step and the last one you
can cheaply redo. Every gate downstream of it — coherence, the derived
rebuild, artifact mix, whatever the world owes its tasks — reads
something the recording produces, and none of them run until the
recording is done.

So record **one day**, export it, and run the entire downstream pipeline
against it before starting the long window. Four separate defects were
found this way in a single pass, each in minutes, each of which would
have cost the whole recording had it surfaced at the end: a validator
missing from one of three write paths, a bound that hid the shared
codes everyone needs, a format the world could never produce because
nothing gave anyone a reason to produce it, and a malformed document in
the world's own definition.

The last one is the sharpest argument for the practice. **It was a defect
in the spec, not in the engine** — the seeded workbook folded its header
into the data rows. It is valid JSON and reads correctly to a human, and
the first thing that would ever have disagreed was the renderer, at
materialization, at the very end.

A one-day world costs a few minutes and exercises every stage. Order the
work so the expensive irreversible step is the *last* thing you start,
not the first.

## Fidelity is measured, not asserted

Commit distribution bands derived from published benchmarks for the
domain — volumes, distribution shapes with anti-uniformity tests,
concentration coefficients, seasonality, cross-surface correlation — and
measure each world against them.

Report three outcomes, not two. **ABSENT — the surface that metric
measures does not exist in the world yet — is a finding, not a skip**,
and the ABSENT column is the build worklist. Folding absent into pass
hides everything you have not built; folding it into fail hides
everything you have.

## Scale

Longer histories are not automatically richer. What makes a long history
worth generating is that it produces relations a short one cannot:
things that recur, escalate, get handed over, lapse, and get corrected.
If six months of generation produces six copies of one month, the extra
cost bought nothing a task can grade.
