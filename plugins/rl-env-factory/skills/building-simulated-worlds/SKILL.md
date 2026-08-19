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
- **Set thresholds between two measured worlds** — a known-bad and a
  known-good — rather than at a round number. A band picked by intuition
  either never fires or fires constantly, and either way stops being
  read.

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
