# This rule admits too much of its own candidate pool

Read before filling `WINDOW_DAYS` on the finished v7 record.

A reader who reports every candidate has recall 1.0 by construction, so its
row F1 is fixed by precision alone — `2p/(p+1)` where `p` is rows ÷
candidates. Measured across twelve tasks in two datasets, that quantity
predicts the measured dump floor at r = 0.892 (see
`docs/fidelity/task-design-laws.md`).

This task's committed probe oracle holds **34 rows against
`questions_read` 102** — `p` = 0.333, a dumped F1 of 0.500, and a measured
dump floor of **0.556**. That is the highest of merrick's three built tasks
and only 0.044 below the line at which the build now prints a warning. It
leaves 0.444 of the scale above what reporting everything already scores.

The cause is not the grading. It is that *a third of the questions in this
firm go unanswered*, so "the unanswered ones" is not a minority of the
pool. Lowering the ratio means a rule that selects a minority **of the
unanswered**, not a different way of counting candidates — recounting the
pool as "messages read" rather than "questions asked" would lower `p` on
paper while the dumper's real strategy is still to report every question,
which is the metric lying rather than the task improving.

## The menu, with yields

Measured on the v6 record over the whole corpus, with a cruder
same-thread reply test than the solver's. **The absolute ratios below are
not this task's ratios** — its oracle is windowed and mine is not, and my
reply detection is weaker, so my baseline reads 219 unanswered of 317
questions where the task's own oracle reads 34 of 102. What transfers is
the *relative* yield of each tightening, since all were measured the same
way on the same corpus:

    rule                                        rows   ratio   dumped F1
    all unanswered (today's rule)                219   0.691     0.817
    ... addressed to exactly one person           218   0.688     0.815
    ... body carries two or more question marks    89   0.281     0.438
    ... in a thread that continued without them    40   0.126     0.224
    ... asked more than once by the same person    32   0.101     0.183

Two of these reach the "under about a tenth" the law asks for, and both
land at 32–40 rows, which is a workable register — `live-commitment-register`
grades 17.

**"In a thread that continued without them" is the better of the two**, on
two grounds beyond the ratio. It is a stronger claim about the world: not
merely that nobody replied, but that the conversation moved on past the
question — a thread that simply died is a weaker finding than one that
carried on around a request. And it is harder to compute in the way this
dataset wants difficulty to be hard: it cannot be settled by looking at the
question's own message, because the evidence is the *later* traffic in the
same thread, which is the same shape as the supersession mechanism that is
the only thing measured to move a frontier model.

"Addressed to exactly one person" is listed because it is the obvious first
idea and it does nothing: 218 of 219, because almost every question here
already has one addressee.

## Do not adopt this from the numbers above

They are v6's, through an approximation. Re-measure on v7 with the task's
own solver before changing the rule, and re-read the floor afterwards — the
relation is a lower bound on the floor, not a prediction of it, and the gap
between the two ran from 0.006 to 0.473 across the twelve tasks measured.
