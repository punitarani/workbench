---
name: iterating-task-difficulty
description: Use when an eval task scores at ceiling or out of its target band and you need to move it - covers which difficulty levers are measured to do nothing, the coverage-versus-rule distinction, and which levers are forbidden. Load before changing a task to change its score.
---

# Moving a score honestly

## The theorem to plan around

> Expert-solvable ⇒ a rule exists ⇒ a frontier model applies it.

This is a definition, not pessimism. "Expert-solvable" means a competent
professional could produce the answer from a stated rule. A frontier model
applies stated rules at roughly 93% per row and does not degrade with row
count. The only ways below that ceiling are to remove the rule — which
destroys expert-solvability — or to grade all-or-nothing, which converts
the measurement into a coin flip.

**Difficulty targets should name a capability tier, not a number in the
abstract.**

## Levers measured to do nothing

Each was built, measured against a frontier model, and came back at
ceiling. Do not spend a build on them again without a reason this list
does not cover.

| lever | how it was tested | result |
|---|---|---|
| volume | contested rows doubled at equal judgment depth | 0.84 → **0.81** |
| depth | four independent judgments per row, traps on 19 of 30 | 0.84 → **0.87** (wrong way) |
| width | 1,300 entries, 27 pages, ~200 rows | ceiling |
| coverage | rows 189 → 507, corpus 328 → 1,547 messages | score went **up** |
| correlated error | a task built for it | 1.000 in 26 shell commands |
| lexical near-miss | 171 near-miss temptations | 1.000 |
| semantic synonym | 70 synonyms excluded by rule | 1.000 |
| chained derivation | three dependent steps per row | **403 of 403** correct |
| office files | 19 workbooks, 61 sheets, no index, nothing queryable | 1.000 |

The mechanism predicts the next failed lever:

> **Deterministic gradeability implies programmatic solvability.**

The oracle is a program, so a task with a deterministic answer key is by
construction reducible to a program — and an agent with a shell will write
one. Scale is then a *cost*, not a difficulty.

What all those levers share: the agent computes each row locally and
mechanically from text already pulled onto disk. Against a written script,
per-row rules are free however long the chain, and independent errors
average out instead of compounding.

## The distinction that does work

Two kinds of difficulty, behaving oppositely under bounding.

**Coverage difficulty** — did the agent enumerate the corpus? Bimodal:
1.000 or ~0.3, decided by whether it finished. It is *luck*, it produces
unstable means, and it **disappears** the moment the corpus is small
enough to finish.

**Rule difficulty** — did the agent apply the stated rule to text it has
already read? A **rate**. One model read 1,574 of 1,585 messages — 99.3%
coverage — and still found 48 of 110 rows, catching 23 of 82 occurrences
of a single common word. **A rate does not care how much text there is**,
so it survives bounding.

This is why "make the corpus small enough that every tier finishes" and
"keep it hard" are not in conflict, once you know which kind you have.

### Why the distinction stays hidden

A frontier model has neither problem, so coverage and rule application
look identical when a model does both perfectly. **Any difficulty
conclusion drawn from a single frontier model is drawn from a sample that
could not have shown otherwise.** Measure at least one tier that fails, or
you are measuring your own ceiling.

## Confusability beats length

The hardest rule measured was the *shortest*: two spellings of one common
word, sitting a hair from its own inflections, missed at 70% by a model
that had read the text. A seven-form list of distinctive date patterns
scored far higher for every tier.

**Fewer forms, more temptation.** Density of near-misses is the variable;
length is not.

## Adding a graded fact widens the gap, it does not lower the mean

Grading "which rule produced this row" cost the weaker tier 0.05 and the
stronger tier nothing — the stronger model had to match the form in order
to emit the row at all, so naming it was free. Extra graded facts are
useful for **discrimination between tiers**, and nearly useless for
pulling a mean down.

## Legitimate levers

- how much of the record a task covers
- how many independent facts per row
- how confusable the rule is
- which capability tier the target is set against

## Forbidden levers

- tightening a tolerance
- reweighting criteria so the same work scores less
- withholding a rule, or trick wording
- grading a fact the surface does not serve

The test: **change what the agent must do, never what the same work is
worth.** A task that scores lower without being harder is a scoring
artifact, and the "calibration" is a property of your grader rather than
of the world.

## When a task sits just outside the band

Say so. A task that measures the same value across three independent
methodological corrections is a stable measurement of something just
outside the target — not a task fighting noise.

Report it out rather than adjusting until it isn't. And if you do apply a
lever, **declare it before seeing which way it moves the result.**
