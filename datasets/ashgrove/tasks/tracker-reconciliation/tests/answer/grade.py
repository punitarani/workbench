"""Answer criteria for the tracker reconciliation.

The weight is on the two numbers per row, not on the verdict word. Four of
five effort rows are `understated`, so an agent that wrote that everywhere
would score most of a verdict criterion while knowing nothing — the hours
are where the work actually shows, and they cannot be guessed.

`hours_understated_total` carries real weight on purpose. It is one number
that only comes out right if every row does, and it is the cheapest way to
catch an answer that looks plausible row by row and is wrong in aggregate.

Tolerances are a hundredth of an hour: enough for a rounding order, not
enough for a row read off the wrong date.
"""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "tracker_reconciliation.json"

rk.scalar(D, "as_of", T["as_of"], name="as_of", weight=0.5)
rk.scalar(
    D,
    "engagements_on_tracker",
    T["engagements_on_tracker"],
    0,
    name="engagements_on_tracker",
    weight=1.0,
)
# The vocabulary decision, as a single number. Read the mapping table
# wrongly in either direction and this is the first thing that says so.
rk.scalar(
    D,
    "engagements_moved",
    T["engagements_moved"],
    0,
    name="engagements_moved",
    weight=2.0,
)
rk.scalar(D, "effort_lines", T["effort_lines"], 0, name="effort_lines", weight=1.5)
rk.scalar(D, "verdict_counts", T["verdict_counts"], name="verdict_counts", weight=1.5)
rk.scalar(
    D,
    "hours_understated_total",
    T["hours_understated_total"],
    0.02,
    name="hours_understated",
    weight=2.0,
)
# Finding the rows at all: the thirteen that are on no line of the sheet
# have to come from clio's side, and they are the difference between
# reading a document and reconciling two records.
rk.flagged_f1(D, T["effort"], name="effort.f1", weight=4.0)
rk.row_fields(
    D,
    T["effort"],
    {"tracker_hours": 0.01, "actual_hours": 0.01, "verdict": 0},
    name="effort_figures",
    weight=6.0,
)
# The other list, keyed on the engagement alone -- a person column would
# collapse ten rows to one.
rk.engagement_fields(D, T["engagements"], name="engagement_status", weight=3.0)
