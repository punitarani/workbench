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
