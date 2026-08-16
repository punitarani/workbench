"""Answer criteria for the time allocation review.

Nearly two hundred rows, so the marks sit on the per-row figures: this
is a task about reading all of the record and doing the arithmetic on
each entry's own rate, and the score should move with how much of that
the agent actually got.

Tolerances are a cent and a hundredth of an hour — enough to forgive a
rounding order, not enough to forgive a page never read.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "time_allocation.json"

rk.scalar(D, "entries_total", T["entries_total"], 0, name="entries_total", weight=1.5)
rk.scalar(D, "pairs", T["pairs"], 0, name="pairs", weight=1.5)
rk.scalar(D, "total_hours", T["total_hours"], 0.02, name="total_hours", weight=1.5)
rk.scalar(
    D,
    "total_billable_hours",
    T["total_billable_hours"],
    0.02,
    name="total_billable_hours",
    weight=1.5,
)
rk.scalar(
    D,
    "total_fees_dollars",
    T["total_fees_dollars"],
    0.01,
    name="total_fees",
    weight=2.0,
)
rk.scalar(D, "busiest_person", T["busiest_person"], name="busiest_person", weight=1.0)
rk.scalar(
    D,
    "busiest_engagement",
    T["busiest_engagement"],
    name="busiest_engagement",
    weight=1.0,
)
rk.flagged_f1(D, T["allocations"], name="allocations.f1", weight=3.0)
rk.row_fields(
    D,
    T["allocations"],
    {
        "person": 0,
        "entries": 0,
        "hours": 0.02,
        "billable_hours": 0.02,
        "fees_dollars": 0.01,
    },
    name="row_figures",
    weight=6.0,
)
