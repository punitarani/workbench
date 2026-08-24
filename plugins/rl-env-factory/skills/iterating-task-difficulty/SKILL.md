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

## A floor is the first thing to move, before any lever

A task cannot be hard for a model if doing nothing already scores in the
band. Measure that before designing difficulty at all: across one shipped
dataset's fifteen keyed tasks, an **empty register with correct scalars
scored a median 0.405**, and "report every candidate" reached **0.990** on
one of them. Every band judgement made there had been made without a floor,
because the tool that computes floors returned an empty dict for that
dataset's task shape and an empty result reads as *no floors exist* rather
than *this function cannot see them*.

The consequence for a three-model mean: on the three tasks that dataset
called in-band, **of six non-frontier scores, three sit inside the range a
no-comprehension dump produces, two sit 0.01–0.06 above it, and one sits
below** — with the frontier model at 1.000 on all three. The band was one
model at ceiling averaged with two scoring where dumping already scores.

So the order is: floor first, then difficulty. A lever applied to a task
whose floor is 0.9 buys nothing.

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

## Confusability beats length — and the operative variable is off-sense share

The hardest rule measured was the *shortest*: two spellings of one common
word, sitting a hair from its own inflections, missed at 70% by a model
that had read the text. A seven-form list of distinctive date patterns
scored far higher for every tier. **Fewer forms, more temptation.**

**Corrected by measurement.** The natural reading of that result — pick
the family with the densest *excluded* near-misses, the inflections a
careless matcher would over-admit — is wrong, and it is wrong in a way
that wastes builds. A machine matching a word boundary is never confused
by a neighbouring inflection; only a human or a model reading for
*meaning* is.

What actually predicts the miss is the **off-sense share of the admitted
form**: how often the required word appears in the corpus meaning
something other than the thing the register is named after. In the family
that produced the hardest measured task, a majority of occurrences of the
admitted word are adjectival (*the complete picture*, *the complete,
dated calendar*), idiomatic, future (*I can typically complete this
analysis*), or conditional (*once that call is complete*) — measured at
79% inside the graded window. Those are precisely the rows the weaker
tiers dropped: a model reading for sense filters them out, and the rule
says they count.

So the selection metric is: **for each candidate family, hand-classify a
sample of admitted-form occurrences as on-sense or off-sense, and choose
the highest off-sense share.** Exclusion density is a decoy — and worse,
it is easy to satisfy with a family that is dead on the actual corpus.
Check both forms are alive before anything else: one family that looked
ideal on paper had its second spelling appear in a single message out of
1,585, and another's in none at all.

Two shapes with the same root, both measured:

- **A form inside a longer phrase**, where the rule admits it and a
  reader hears a hedge (`within a day` inside *"within a day or two"*).
- **One sentence carrying two forms that resolve to different values**,
  where the second reads as an explanation of the first. Every trial
  found the first; two of nine found the second.

## Adding a graded fact widens the gap, it does not lower the mean

Grading "which rule produced this row" cost the weaker tier 0.05 and the
stronger tier nothing — the stronger model had to match the form in order
to emit the row at all, so naming it was free. Extra graded facts are
useful for **discrimination between tiers**, and nearly useless for
pulling a mean down.

## Do the band's arithmetic before designing for it

A three-model mean with a frontier tier pinned at 1.000 is not a target
on all three models — it is a budget on the other two. For a ceiling of
0.8:

    mean = (1.000 + a + b) / 3 <= 0.80   <=>   a + b <= 1.40

Every task measured in band on one suite has the frontier at 1.000; what
separated in from out was entirely the weaker pair's sum, and the
boundary is about 0.05 wide. Three in-band tasks summed 0.73, 1.32 and
1.38; the one that missed summed 1.43.

Two consequences worth internalising before a build:

- **"A frontier model would score 1.000" is not, by itself, a rejection.**
  It is the expected case, and the design question is what the *named*
  weaker tiers do. Treat frontier 1.000 as a defect only when the
  frontier *misses* — because then the miss is far more likely to be a
  task defect than a capability limit.
- **The margin is thin, so measure the mechanism before building.** At a
  0.05-wide boundary, an unmeasured guess about difficulty is a coin
  flip, and the honest response to landing at 0.81 is to report it rather
  than to lever it.

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

## A band can be manufactured entirely by the answer key

The most expensive way to be wrong about difficulty: a task sits at
0.33-0.51 across three model families, looks perfectly calibrated, and is
measuring its own defects.

The tell is available before any lever is chosen. **Decompose the loss
per criterion.** If a scalar reads 0.0 for every trial of every model
while the counts-of-what-was-read read 1.0, the models opened the whole
corpus and disagree with the key, not with each other. On one task
`superseded_count` and `distinct_owners` were 0.0 in nine of nine trials
while `meetings_read` and `turns_read` were exact.

Then check recall against the subset of the key you can defend by
reading the source. the strongest tier scored 10/10, 9/10, 10/10 there while
its graded `live.f1` read 0.53-0.59 — and it was 100% correct on every
evidence field of every row it matched. The reward said 0.508; the model
was at ceiling.

**Correct the key before choosing a lever**, even though correcting it
raises the scores — that is the point. A lever applied on top of a broken
key tunes the defect.

And be ready for the honest outcome: once corrected, that task ran
0.838/0.838/0.838 for the frontier tier. Identical three times, one
genuine row error, the rest an exact-match integer. The apparent band was
gone and the real difficulty was small. **Report that rather than
re-widening the window to recover a number** — the window levers under a
word ceiling move supersession density by fractions, and coverage was
already measured not to survive.
