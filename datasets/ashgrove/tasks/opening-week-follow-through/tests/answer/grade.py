"""Answer criteria for the follow-through review.

Three chained judgements per row -- find the promise, resolve its date,
then look forward for the author -- so the weight sits on the row set and
the per-row facts, where a mistake at any step lands.

`followed_up` splits 56 to 58, so neither verdict is worth guessing, and
the two counts are the cheapest way to catch a register that looks
plausible row by row and is wrong in aggregate.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "opening_week.json"

rk.scalar(D, "messages_read", T["messages_read"], 0, name="messages_read", weight=1.0)
rk.scalar(
    D,
    "commitments_total",
    T["commitments_total"],
    0,
    name="commitments_total",
    weight=2.0,
)
rk.scalar(
    D,
    "followed_up_count",
    T["followed_up_count"],
    0,
    name="followed_up_count",
    weight=2.0,
)
rk.scalar(
    D, "unanswered_count", T["unanswered_count"], 0, name="unanswered_count", weight=2.0
)
rk.scalar(D, "worst_offender", T["worst_offender"], name="worst_offender", weight=1.0)
rk.flagged_f1(D, T["commitments"], name="commitments.f1", weight=5.0)
rk.row_fields(
    D,
    T["commitments"],
    {"author": 0, "sent_date": 0, "followed_up": 0},
    name="row_facts",
    weight=6.0,
)
