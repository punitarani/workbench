# A practitioner's review of the blocker register, answered with measurements

A reviewer with legal-ops knowledge read `blocker-register` and judged it
**partly realistic**: the work product is a real artifact — a pre-partner
"what is stuck" list — but the assignment as written is not something a
lawyer or paralegal would be given, or would execute this way.

Every criticism was correct as stated. Three of them turn out to be
ungradeable when measured, one is a genuine defect with a cheap fix, and
one produced a new task. This file records which is which, with the
numbers, so the same argument does not have to be had again from scratch.

---

## 1. "Rows should be ISSUES, not person × series" — correct, and not gradeable here

> *A real register tracks issues (matter + bottleneck). This tracks person ×
> meeting series: Elena's nine raises from January to May can be nine
> different waits. A useful chain puzzle; a bad operations report.*

Right on both counts. It was measured rather than argued.

To key a row on the matter, the oracle has to derive the matter from the
same clause that carries the complaint. On this corpus:

| | |
|---|---|
| blocked turns | 75 |
| naming a matter anywhere in the turn | 29 (50%) |
| naming a matter **in the complaint clause** | 6 (**10%**) |
| spoken labels that resolve to more than one matter | 21 of 22 |

Ten per cent, and the labels are ambiguous besides — "Coastal Meridian"
names two matters and "Halden Orthopedics" three.

This is L7: **a key component the model cannot derive is one the ORACLE
cannot derive either**, with its corollary that a conjunctive rule is safe
only when its conjuncts share a unit. *Who is stuck* is a property of the
clause; *which matter* is a property of the turn or of a different clause
entirely. Keying on both grades a reader wrong for reading correctly.

The same measurement killed matter-keying for the commitment registers a
month earlier — 63 of 178 turns named a matter, at a median 96 characters
from the commitment. Two independent attempts, same wall.

**Answer: the criticism is right and the fix is not available on this
corpus.** A world would have to be recorded where people say what they are
blocked on in the clause where they say they are blocked. That is a world
change, not a task change, and it is the honest way to fix it.

## 2. "Shrink the window to recent cycles" — correct, and it empties the register

> *A human would use last week's notes or the last few instances of each
> series. They would not re-read every standing meeting with no index.*

Also right about how the work is really done. Measured, on the last N
occurrences of each standing series:

| window | meetings | rows | median raises |
|---|---|---|---|
| last 4 | 32 | **2** | 1.0 |
| last 8 | 64 | **3** | 1.0 |
| last 12 | 96 | **5** | 1.0 |
| whole window | 520 | 22 | 2.0 |

*(Re-measured 2026-08-29, after the blocker rule was corrected in seven
ways. Every figure moved up by one or two and the conclusion did not move
at all: at the realistic slice the register still has two or three rows,
and a register with three rows cannot score partially.)*

At the realistic slice there are two rows. Blockers are rare — 75 turns in
2,872 — so the phenomenon's density sets a floor under the window, and
realism cannot go below it.

**Answer: the wide window is not convenience, it is arithmetic.** A task
whose register has two rows cannot score partially; every rollout comes
back 0 or 1. The honest statement is that this measures a capability a
human would not be asked to exercise at this scale, which is true of most
agent benchmarks and worth saying out loud rather than dressing up.

## 3. "The closed phrase grammar is not how lawyers read" — correct, and deliberate

> *The inclusion rule is a closed collocation list plus clause tests.
> Lawyers use judgment. Those rules exist so an oracle and a solver can
> agree.*

Exactly so, and the brief states the list rather than hiding it — which
makes this a **specification-following** task, not a judgement task. That
is a smaller claim than "reads like a lawyer" and it should be made
plainly. A judgement-graded version would need an LLM judge, and this tree
has a measured law about what that costs: a check that cannot disagree with
the thing it checks is not a check.

**Answer: reclassified rather than fixed.** The skill being measured is
exhaustive application of a stated rule across a corpus no script can
flatten — not legal judgement.

## 4. "Six systems listed, then told the answer is only in transcripts" — a real defect

> *You would not list six systems and then say the answer is only in
> transcripts. The extra tools are distractors.*

This one is straightforwardly wrong in the brief and cheap to fix. Telling
the agent where to look removes the tool-selection problem that the six
surfaces exist to pose, and no real brief would do it.

**Answer: fixed.** The hint comes out. A competent reader should have to
discover that Clio's statuses do not carry this and the transcripts do.

## 5. "The deliverable is a transcript census, not a memo" — half fixed

> *Partners want a table or a short memo. `meetings_read`, `turns_read` and
> meeting IDs are audit fields.*

Right that no partner wants them. They are graded because they are the one
signal that separates a reader who opened the whole window from one who
sampled, and because a register with no evidence fields has a per-row
criterion that cannot fail — measured: with an empty field set, an empty
answer scored 0.500.

**Answer: partly.** The counts move to the diagnostic dimension, where they
inform without paying; the meeting IDs stay, because they are what makes a
chain checkable.

## 6. "A standing meeting is a title on three or more days" — a dataset filter

> *That is not how firms define recurrences. Those already sit on the
> calendar as series.*

Correct, and the cause is an engine defect rather than a task decision:
`event_recurrence` is a real table with **0 rows**, the workplace spec
declares these meetings `daily` and `weekly`, and the projection never
writes it. The world log carries no recurrence either, so serving it
properly needs a re-recording.

**Answer: acknowledged, not fixed.** Recorded as an engine defect. Note
that `meetings_read` scores 1.000 for every tier, so deriving the standing
set is not where difficulty lives — this is a realism cost, not a
measurement one.

---

## What the review produced, and what it did not

The first draft of this file proposed a second task: split a person's chain
wherever it goes quiet for more than sixty days, on the grounds that a wait
which stops for two months and comes back is a different wait, and the gap
needs no matter to derive. It called that "the gradeable half of criticism
1" and said it would ship beside the original.

**Measured, it is a worse task, and the claim above was wrong.**

| split | rows | median length | single-raise rows |
|---|---|---|---|
| none (person × series) | 20 | 2.0 | 9 of 20 |
| 60-day gap | 28 | 1.0 | **18 of 28** |
| 21-day gap | 40 | 1.0 | — |

Splitting turns a chain into episodes, and on this corpus most episodes are
one raise long. That hands the task to a strategy with no chain
reconstruction in it at all — report every complaint as its own episode,
`first == last`, `count == 1`:

    every-complaint-is-an-episode      f1 = 0.434
    (the same strategy against the unsplit register)   f1 = 0.000

Forty-three per cent of the row set, for never grouping anything. The
unsplit register gives that strategy nothing, because every one of its rows
spans meetings that have to be found and ordered first.

**So the faithful row definition is the less measurable one here**, and the
reason is the same rarity that forced the wide window: blockers are sparse
enough that episodes are mostly singletons. The task keeps person × series
and the report says plainly that a person's chain may conflate distinct
waits.

That is the honest resolution of criticism 1. Not "the reviewer was wrong"
— they were right about the artifact — but the fix they imply is not
available on a corpus this sparse, and the version that looks more like an
operations report measures less.
