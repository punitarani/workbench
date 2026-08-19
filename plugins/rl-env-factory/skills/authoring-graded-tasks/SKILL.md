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
