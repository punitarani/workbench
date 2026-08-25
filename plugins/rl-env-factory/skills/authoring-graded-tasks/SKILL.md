---
name: authoring-graded-tasks
description: Use when writing an eval task instruction, oracle, or grader over a simulated world - covers the brief, declaring the rule kind, structural floors, deliverable shape, and bounding the work. Load before writing instruction.md or a solver.
---

# Cutting a task from a world

## The instruction is a brief, not a spec

It is the only prose the agent gets. It must read as a colleague's
handoff: who you are, what happened, the precise professional rule that
defines the answer set, and the deliverable's name and shape.

**Never name the scaffolding** — no databases, no servers, no grading,
nothing revealing the work is scored. A rule that fixes an exact answer
set is a professional standard; phrase it the way the institution would.

## State the rule, then state which *kind* of rule it is

The most expensive defect class there is, found five times on five tasks
in one suite: an instruction whose *prose* describes a concept and whose
*test* is string matching. The two disagree, a careful reader trusts the
concept, and the grader trusts the string — **so the model that read more
carefully loses points.**

Each of these cost a measurement:

- a register of *promises* whose rule matches tokens anywhere in a body
- "that message *asks for something*", implemented as twelve phrases,
  where `we need` also appears inside "what we need to deliver"
- "work reported *complete*", implemented as the word `complete`, which
  also matches "that gives you the complete picture"

**If the rule matches words in prose, the instruction must say the test
is textual and not editorial** — in the instruction, not in the solver's
comments.

There is a second, distinct version: whether a form *inside a longer
phrase* still counts (`within a day` inside "within a day or two").
Saying "textual, not editorial" does not settle that one. Say it
separately.

## What actually decides whether a frontier model sits at ceiling

Five register tasks over one corpus, all built the same way, all with
correct answer keys. Four scored **1.000** for the strongest tier. One
scored 0.766. The difference is not the rule, and finding that out cost
four sweeps.

**It is not corpus size.** The ceiling tasks read 195, 280, 530 and 623
items. The one that measures reads 623.

**It is not arithmetic.** One ceiling task resolves three-working-day
deadlines with weekend skipping. Another resolves seven relative date forms.

**It is not rule subtlety on its own.** A register whose rule is five
semantic conditions on where a date sits relative to a promise scored
1.000 on mail and 0.766 on meeting transcripts. Same rule, same
implementation, same corpus, different surface.

**What separates them is whether the GROUPING KEY is a field or a
derivation.**

    mail      owner   <- a column on the message
              due     <- computed from the text
              => group by a column, take the max. One row per person.

    meetings  owner   <- a column on the utterance
              meeting <- DERIVED: of 52 distinct titles across 567
                         meetings, a title is a "standing series" only if it
                         appears on three or more days in the window. 44 of
                         the 52 are one-offs and make no rows at all.
              due     <- computed from the text
              => derive the series first, discard the one-offs, group into
                 eight, and only then supersede within each group.

The mail task collapses because the agent can group by a field. It pulled
530 messages in twelve `search_threads` calls and did the rest in 118 shell
commands. The meetings task cannot be grouped without first computing which
titles are series, and an error there does not produce a wrong value -- it
silently merges two groups or drops one, which changes the row SET.

**So the design lever is: make a key component something the corpus does
not state.** A key the agent must compute has an error rate; a key it can
read does not. And errors in a derived key cost rows rather than fields,
which is what row-F1 is sensitive to.

Corollaries worth stating, because each one cost a sweep:

- **A key with one row per person is nearly free.** Enumerate the people,
  and the row set is done; only the value is at stake. Check
  rows-per-owner before building: 1.00 is a warning, 1.17 was enough.
- **A bulk-readable surface defeats incremental reading.** If one tool call
  returns a hundred bodies, the agent will pull the corpus and script it.
  A surface that serves one item per call keeps the work in the loop.
- **Porting a rule to a new surface does not port its difficulty.** Screen
  the port; do not assume it inherits the band.

## Derivability and gradability pull against each other

The law above says a key component the agent must COMPUTE is what makes a
task hard. The obvious next move is to derive more of the key, and it has a
limit worth knowing before you spend a day on it.

A register was designed to derive BOTH halves: not "what did the speaker
promise" but "what does the room say each PERSON owes", so the owner comes
out of the text instead of off a column. The survey numbers were the best
of any candidate -- rows per owner 2.45 against the working task's 1.17,
repeat rate 71%.

It does not survive contact with the prose. The dominant shapes are all
cases where the named person is not the owner:

    "...have a date to Thandiwe by tomorrow"     Thandiwe is the RECIPIENT
    "Dov, do you want that before Friday?"       a question, and Friday
                                                 belongs to a closing
    "I'll chase Ulrich again ... by end of day"  Ulrich is the OBJECT

255 of 302 candidates were one of these. Restricting to an unambiguous
anchor -- a named person as the subject of a future verb, the third-person
mirror of `I'll` -- leaves **one** instance in the whole corpus. People
speak in the first person about their own work.

**The commitment rule works because `I'll` is an unambiguous anchor for
ownership.** Take the anchor away and the rule does not become harder, it
becomes ungradable: a key component the model cannot reliably derive is one
the ORACLE cannot reliably derive either, and the oracle has to be right.

So the test for a derived key component is not "is it hard to compute". It
is **"is there an anchor that makes the right answer decidable"**. A
derivation with an anchor is difficulty. A derivation without one is a coin
flip you will spend three sweeps mistaking for difficulty.

Cost of learning this the cheap way: twenty minutes of measurement against
the corpus. Cost of learning it the expensive way, on the register before
it: a build, a screen, and a day of adjudication.

## Check the rule against the corpus before shipping it

Count how the world actually writes the thing before fixing the rule's
vocabulary. One rule required an article the corpus used **once** while
the institution wrote the bare form 34 times — so it admitted 1 of 35
real instances and scored the other 34 as hallucinations.

Your intuition about how people write is not evidence. A frequency count
over the corpus is, and it costs one query.

The same check governs moving a rule to a new grain: **a literalism task
is only hard where the near-misses are dense**, so measure the near-miss
ratio there first.

## Screen the answer's share of the candidate pool before building

A reader who reports every candidate has recall 1.0 by construction, so
its row F1 is fixed by precision alone — `2p/(p+1)` where `p` is rows ÷
candidates. Across twelve tasks in two datasets that predicted quantity
correlated with the **measured** dump floor at **r = 0.892**:

    rows/candidates   dumped F1   measured dump floor
    0.07-0.15           0.13-0.26        0.36-0.64
    0.28-0.48           0.44-0.65        0.66-0.75
    0.88-0.90           0.94-0.95        0.95-0.99

One shipped task admitted **43 of its 49 candidates** — reporting
everything was 88% right before anything was read — and paid a dump 0.990.
That is not a grading bug: a rule admitting nine candidates in ten cannot
punish admitting all ten.

`rows / candidates` is knowable from a **design**, before a world is
recorded or a rollout paid for. Keep the answer under about a tenth of the
pool. The relation is a lower bound on the floor, not a prediction of it —
the gap ran 0.006 to 0.473 — so still measure.

**Which pool you declare decides the floor you measure**, and the wider
declaration flatters the task. One register read 0.099 against every mail
message and 0.384 against the messages carrying a date, which is the set a
dumper actually submits. Screen against the narrowest pool a competent
reader could filter to in one pass.

That is usually nobody's cheating. A report's `*_read` figure often
measures **work done** — one task counted every message in its window
precisely so an agent had to open the window rather than grep it — while
the dump pool wants the candidates a cheap filter leaves. The two coincide
only when the rule admits from everything it opens.

## A floor is a bracket, and the end you quote decides your conclusion

"Report every candidate" scores one value with its own counts wrong and
another handed the true scalars. Both are defensible. Same two model
scores on one task read as *both models partially succeeded* against the
empty-register floor, and as *one clears by 0.085, the other sits 0.012
below* against the top of the dump bracket. Quote both ends.

And build the **competent** dump, not a strawman. A baseline that pads the
true rows with random noise sized from a work-measure is a weak dumper:
its noise matches no key. The recipe is general even though the filter is
not — fill the task for a window and run its own solver against the
bundle, whose output **is** the answer key for that window, then build the
answer a reader would submit after one cheap pass and score both through
the task's own grader. Measured that way on one task: strawman 0.366,
competent 0.419.

Note what that comparison also teaches. The row-F1 ratio between those two
dumps was 4.4x and the score difference was 0.053 — because row F1 carried
5 of about 11 weight and the extra-row penalty was capped. **A ratio on one
criterion is not a ratio on the score.**

## The screen that picks the window must use the rule the task grades

A window screen counted a commitment as an owner form *somewhere* in a turn
and a deadline *somewhere* in it. The task required both in one sentence.
On the same window the screen reported 21 rows where the oracle held 15 —
a 40% overstatement in the exact number its row floor was checked against,
so a window it called usable at 13 could build 9 and be refused one step
after the decision that caused it.

Correcting it changed the answer: the window that looked best at a 14%
guessing floor became 20%, and a different window at 10% won. **Two
derivations of "the same" quantity, one used as a gate for the other, is
the defect to look for whenever a screen and a grader were written apart.**

## Choose a window on the guessing floor, not the row count

The row count says whether a register can score partially. The **guessing
floor** — the share of a graded field reachable by writing the commonest
value without reading anything — says how much of the answer is free. Five
windows over one corpus all cleared the row floor; their guessing floors
ranged 10% to 24%, and the one with the most rows was not the best.

## Build only on joins the world records explicitly

If a relation has to be *inferred* — which parent record a document
belongs to, which contact counts as the client — the oracle built on it
is not deterministic, and the disagreement surfaces as a model failure.
Either the world records the relation as a field, or the task does not
grade it.

## The deliverable's shape must not answer the question

**A schema that names each half of a distinction has given the
distinction away.** A rule says what the answer *is*; a procedure says
where to *look*. State the first, never the second, and check that the
output shape does not decompose the judgment the task exists to measure.

## Every decision the rule leaves open is a coin flip

An agent cannot win an unstated choice by working harder.

- Enumerate the vocabulary of any object-valued field and require every
  key, including zero-valued ones.
- Fix every tie-break and ordering in the instruction.
- Name the units, and the rounding order — adding durations then rounding
  is not the same as rounding then adding, and on a real record the two
  disagree on a third of rows.

If two defensible answers exist, the task measures which one the agent
guessed.

## Structural floors

| floor | why |
|---|---|
| ≥ 12 rows | fewer cannot express partial credit; the task reads 1.000 or near zero with nothing between |
| no constant-valued graded field | a column with one value grades nothing — an agent that never looks scores full marks |
| every graded value reachable through the served surface | a rule the agent cannot evaluate through the tools is not a task rule |
| exact-match aggregates alongside row F1 | one wrong row should move several criteria; this is what turns a small real error into a mid-band score |
| the reference answer scores 1.000 against its own grader | otherwise the ceiling is not 1.0 and every score below it is misread |

## Bound the work, not only the answer

If a task reports a figure computed over the whole corpus — "how many
records you examined" — the agent will examine the whole corpus, even
when the answer set is a small window of it. On a large corpus that alone
can take a model from a good score to **no deliverable at all**.

Bound what must be read, not just what must be reported.
