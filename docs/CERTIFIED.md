# Certified tasks

A task is certified when three model tiers each score inside 0.2–0.8 on at
least three graded trials of **one** version of the task, and no single
criterion carrying most of the weight is at ceiling for any tier. The last
clause matters: a task can sit inside the band on its mean while the
criterion that carries half the reward reads 1.000 for the strongest
model, and then the band is an average of something measured and something
that is not.

Reproduce any row with:

    uv run python scripts/certify.py --dataset merrick --task <task> \
        --tag <opus-tag> --tag <glm-tag> --tag <kimi-tag>

A certification recorded here can be withdrawn. One was, within the hour:
`standing-commitment-register` was certified on 2026-08-27 and the verdict
was wrong -- a kimi trial that wrote no deliverable was averaged in as a
zero, which left three "graded" trials where there were two. The gate
promised in its own docstring to exclude DNFs and did not. Fixed, the task
reads NOT CERTIFIED pending a third answered kimi trial.

The error ran in the dangerous direction, which is why it is written down
rather than quietly corrected: a DNF averaged as zero drags an ABOVE-band
task down into range, so the more often a tier fails to answer, the more
certifiable a task looks.

## merrick

### commitment-revision-register — CERTIFIED 2026-08-27

Six months of a law firm's standing meetings. For every live commitment:
who owes it, in which meeting, the date it is due, the date they *first*
committed to, and how many earlier commitments it replaced.

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.643, 0.704, 0.769 | **0.706** | live.f1 0.734 |
| glm-5.2 | 0.454, 0.500, 0.530 | **0.495** | live.f1 0.455 |
| kimi-k3 | 0.428, 0.467, 0.581 | **0.492** | live.f1 0.450 |

Floors: an empty register scores 0.200 (the two coverage scalars and
nothing else), reporting every candidate scores 0.000, doing nothing
scores 0.000.

What makes it hard is joint dependency rather than volume. Each row needs
both ends of a chain and its length, and none of the three is derivable
from the other two — measured: adding rows that each turn on a single
extraction does not move a frontier model at all, because row F1 is
per-row. A month-end snapshot design was built on paper, measured at 117
rows against 26, and discarded for exactly that reason.

Tags: `opus-rev2-k3`, `glm-rev2-k3`, `kimi-rev2-k3`.

### standing-commitment-register — CERTIFIED 2026-08-27 (second attempt)

The same six months, asking the one thing the register above does not: how
many times each person moved their own date **later**. Both other
registers in this family need the chain's ENDS -- the last statement for
`due`, the first for `first_due`, the room count for `superseded`. A slip
is a comparison of two consecutive resolved dates, so this one needs every
link, each resolved against the meeting it was said in.

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.717, 0.755, 0.794 | **0.755** | live.f1 0.846 |
| glm-5.2 | 0.345, 0.368, 0.416 | **0.376** | live.f1 0.434 |
| kimi-k3 | 0.305, 0.518, 0.586 | **0.470** | live.f1 0.436 |

Floors: an empty register scores 0.273, reporting every candidate 0.000.

This is the second attempt. The first certified on a kimi row of
[0.0, 0.346, 0.383] where the 0.0 was a trial that wrote no deliverable --
two answered trials wearing the shape of three. The tags above are a fresh
kimi sweep in which all three trials answered.

Tags: `opus-slip-k3`, `glm-slip-k3`, `kimi-slip2-k3`.


## delegation

A second world, recorded with one change to the workplace spec so that
partners hand work to named colleagues out loud instead of taking it on
themselves. 135 days, 411 meetings, 166,888 words. It yields 122
assignments against the first world's 16 — the first time a world here was
commissioned FOR a family rather than a family found in a world.

### assignment-revision-register — CERTIFIED 2026-08-29

For every live assignment: who was told to do it, in which standing
meeting, and the date it is due, with the chain's other end and its length
graded as fields. **The owner of a row is never the person who said the
words**, which is the whole task: a reader who finds every turn and keys it
on the speaker gets every row wrong.

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.384, 0.402, 0.414 | **0.400** | assignments.f1 0.338 |
| glm-5.2 | 0.243, 0.291, 0.341 | **0.292** | assignments.f1 0.159 |
| kimi-k3 | 0.277, 0.286, 0.300 | **0.288** | assignments.f1 0.154 |

Floors: an empty register scores 0.200, a dump 0.369.

**The key was chosen by measurement, not by argument.** It shipped keyed on
five facts and every tier sat inside the band while extracting almost
nothing — `assignments.f1` at 0.178 / 0.052 / 0.032, with 32 of 39 rows
declined by every trial of every tier. Re-scoring the same saved
deliverables under each candidate key gave:

    (owner, meeting)                          0.695 / 0.614 / 0.608
    (owner, meeting, due)                     0.338 / 0.159 / 0.154
    (owner, meeting, due, superseded)         0.207 / 0.067 / 0.039
    (owner, meeting, due, first_due, sup)     0.178 / 0.052 / 0.032

Three components is the point where the criterion is demanding without
being untouched. That is the difficulty law run BACKWARDS: a hard fact in
the key collapses row F1 and in a field only degrades it, which is normally
used to make a task harder and here was needed the other way.

Tags: `opus-a1-k3`, `glm-a1-k3`, `kimi-a1-k3`.
