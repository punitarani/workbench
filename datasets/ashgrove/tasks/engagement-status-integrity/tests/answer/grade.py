"""Answer criteria for the regression review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "status_integrity.json"

rk.scalar(
    D, "engagements_reviewed", T["engagements_reviewed"], name="reviewed", weight=1.0
)
rk.scalar(D, "reopened_count", T["reopened_count"], name="reopened", weight=2.0)
rk.scalar(
    D,
    "backward_move_count",
    T["backward_move_count"],
    name="backward_moves",
    weight=2.5,
)
rk.scalar(
    D, "never_moved_count", T["never_moved_count"], name="never_moved", weight=1.5
)
rk.flagged_f1(D, T["flagged"], name="flagged.f1", weight=3.0)
rk.row_fields(
    D,
    T["flagged"],
    [
        "status",
        "status_changes",
        "backward_moves",
        "reopened",
        "hours_after_first_backward",
    ],
    name="row_facts",
    weight=5.0,
)
