"""Answer criteria for the staffing leverage review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "leverage.json"

rk.scalar(
    D,
    "engagements_reviewed",
    T["engagements_reviewed"],
    0,
    name="engagements_reviewed",
    weight=1.0,
)
rk.scalar(
    D,
    "firm_leverage_ratio",
    T["firm_leverage_ratio"],
    0.02,
    name="firm_leverage_ratio",
    weight=2.0,
)
rk.id_set_f1(
    D, "over_supervised", T["over_supervised"], name="over_supervised.f1", weight=3.0
)
rk.row_fields(
    D,
    T["engagements"],
    {
        "partner_hours": 0.05,
        "manager_hours": 0.05,
        "senior_hours": 0.05,
        "staff_hours": 0.05,
        "support_hours": 0.05,
        "leverage_ratio": 0.02,
        "review_share_pct": 0.2,
    },
    name="row_figures",
    weight=6.0,
)
