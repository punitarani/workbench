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

### standing-commitment-register — CERTIFIED 2026-08-27, re-certified 2026-08-29

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

**Re-certified 2026-08-29** after `meetings_read` left the reward. It read
1.00 for all three tiers -- at ceiling, so measuring none of them -- and
counting the meetings in a stated window is a date-filtered query.

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.689, 0.731, 0.773 | **0.731** | live.f1 0.846 |
| glm-5.2 | 0.279, 0.304, 0.358 | **0.314** | live.f1 0.434 |
| kimi-k3 | 0.235, 0.470, 0.545 | **0.417** | live.f1 0.436 |

`superseded_count` stays, and it reads 0.00 for nearly every tier of every
tag. That looks like a criterion nobody can score and is not one: the
oracle holds 128, the trials report 121 to 129, and three of them reported
exactly 128. It is scored exact, so counting almost all of the
supersessions earns nothing. Hard, not unmeasurable, and the test for
which is whether anybody has ever scored it.

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

**Re-certified 2026-08-29 after the first certification was withdrawn.**
The original rested on two of ten points that every tier earns for reading
the window — census counts a practitioner review correctly called audit
fields nobody wants. With those moved to the diagnostic dimension the same
task read 0.259 / 0.102 / 0.098, two tiers below band, and the propping-up
became visible.

The key was then rebuilt around ATTRIBUTION, which is what the family is
about, and the rule was corrected on ten defects found by adjudicating rows
every trial declined. Final:

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.469, 0.474, 0.489 | **0.477** | assignments.f1 0.759 |
| glm-5.2 | 0.375, 0.386, 0.434 | **0.398** | assignments.f1 0.663 |
| kimi-k3 | 0.372, 0.394, 0.398 | **0.388** | assignments.f1 0.658 |

Five rows are waived as model failures, adjudicated one by one in
`docs/adjudications/delegation-assignment-flagged-rows.md` with the
sentence behind each. Ten others in the same set were oracle defects and
were fixed rather than waived.

Tags: `opus-a1-k3`, `glm-a1-k3`, `kimi-a1-k3`.


### delegation/commitment-revision-register — CERTIFIED 2026-08-29

The promise rule on the second world. Same family as merrick's, and harder
because the world is denser: **200 commitments in 383 meetings** against
154 in 512, so the same key costs more here.

| tier | trials | mean | heaviest criterion |
|---|---|---|---|
| opus-5 | 0.483, 0.551, 0.618 | **0.551** | live.f1 0.704 |
| glm-5.2 | 0.269, 0.369, 0.467 | **0.368** | live.f1 0.518 |
| kimi-k3 | 0.185, 0.200, 0.408 | **0.265** | live.f1 0.370 |

Keyed on `(owner, meeting, due, first_due)` — four components, chosen by
re-scoring the same saved deliverables under every candidate rather than by
argument. At five the weakest tier's criterion read 0.261 and its headline
fell below the band; at three the key stops asking for the chain at all.

Five rows are waived as model failures, adjudicated in
`docs/adjudications/delegation-commitment-first-due.md`. All five are one
error with several faces: three claim a `first_due` **no commitment in that
series resolves to** — a meeting date, or the window's first day — and one
reports the chain's last element as its first. Nine of nine trials agreed
on one of them, which is the strongest unanimity signal here and still not
a defect: a shared misreading of a SCOPE produces the same wrong answer
every time and looks exactly like a key defect.

Tags: `opus-c1-k3`, `glm-c2-k3`, `kimi-c1-k3`.
