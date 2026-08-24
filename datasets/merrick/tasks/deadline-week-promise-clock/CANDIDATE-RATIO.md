# Declare the honest pool, and consider grading the minority half

Read before building this task on the finished v7 record.

## The pool it declares decides the floor it measures

A dump baseline is sized from the candidate count the report states. This
task's candidates can be described two ways, and they measure nearly 0.3
apart:

    declared pool                            rows   ratio   dumped F1
    every mail message                 707    158   0.223     0.365
    messages carrying any relative date 332   158   0.476     0.645

**Which figure the solver actually reports, checked 2026-08-23.**
`solve.py:374-383` counts `read` for **every message inside the window**,
and the comment above it says why: *"Requiring a figure over the whole
record is what makes an agent read the whole record: the bound has to apply
to the work and not only to the answer."* That is a deliberate and correct
purpose, and it is not the same purpose the dump floor needs.

So this is not a task gaming its floor. It is `baselines.measure` picking
`*_read` as the candidate pool, when a report's read-count measures **work
done** and the dump pool wants **candidates a cheap filter leaves**. The
two coincide only when the rule admits from everything it opens. Here they
differ by four times, and the task is the innocent party.

There is no mechanical fix, for the reason the gate already prints: bounding
the real floor means knowing which pre-filters are cheap for a reader, and
that is a judgement about the corpus rather than a property of the oracle.
What follows from it is a rule for reading, not a patch — **a floor
computed from a work-measure is a lower bound on the floor, and the gap is
whatever the rule filters out for free.**

**The second is the honest one.** A reader dumping this task submits
messages that carry a date, not every message in the firm — the report asks
for dated promises, so filtering to dates is one cheap pass, not
comprehension. Declaring 707 would measure a comfortable 0.365 while the
real floor is 0.645, and the build gate would print the comfortable number.
That direction of error is the one to watch: a generous candidate count
makes a task *look* better here while being no harder to dump.

At the honest pool this task trips the build's warning line (0.6) with only
0.355 of the scale above what reporting everything already scores.

## Its own forward join is the better register

`followed_up` is the field the design is proud of — it cannot be read off
the message that carries the promise, only out of later traffic in the same
thread. Today it is a *field* on a row; it could be the *rule*:

    rows                                     rows   ratio   dumped F1
    every promise (today's rule)              158   0.476     0.645
    promises the writer NEVER came back on    102   0.307     0.470
    promises the writer DID come back on       56   0.169     0.289

The minority class is the kept promise, not the broken one: only about a
third of promises here get a follow-up in the same thread. Grading those 56
more than halves the dumped F1, from 0.645 to 0.289, and it keeps the
property the task exists for — the evidence is in later traffic, so a
reader that stops at the window boundary gets every row wrong rather than
every boolean wrong.

Neither split reaches the "under about a tenth" the law asks for. 0.169 is
a real improvement and not a clean pass, and it should be measured again
rather than assumed: see `unanswered-question-register/CANDIDATE-RATIO.md`
for the same screen on that task, where the two best tightenings do reach
0.10–0.13.

## These numbers are approximations

Measured on v6 with a promise pattern and a follow-up test written for this
note, not with the task's own solver, so treat the *relative* yields as the
finding and re-measure the absolutes on v7. The candidate-ratio relation is
in any case a lower bound on the floor rather than a prediction of it —
across the twelve tasks it was fitted on, the measured floor sat between
0.006 and 0.473 above what the ratio alone predicts.
