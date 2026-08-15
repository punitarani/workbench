"""Answer criteria for the engagement status review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "closeout.json"

rk.scalar(
    D,
    "client_engagements",
    T["client_engagements"],
    0,
    name="client_engagements",
    weight=1.0,
)
rk.scalar(D, "status_counts", T["status_counts"], name="status_counts", weight=1.5)
rk.scalar(
    D,
    "longest_waiting_engagement",
    T["longest_waiting_engagement"],
    name="longest_waiting_engagement",
    weight=1.0,
)
rk.id_set_f1(
    D,
    "awaiting_firm_reply",
    T["awaiting_firm_reply"],
    name="awaiting_firm_reply.f1",
    weight=3.0,
)
rk.scalar(
    D,
    "wip_at_risk_dollars",
    T["wip_at_risk_dollars"],
    5.0,
    name="wip_at_risk",
    weight=2.0,
)
rk.id_set_f1(
    D, "at_risk_over_10k", T["at_risk_over_10k"], name="at_risk_over_10k.f1", weight=2.0
)
rk.row_fields(
    D,
    T["engagements"],
    {
        "client_contact": 0,
        "responsible": 0,
        "total_hours": 0.05,
        "staff_count": 0,
        "status": 0,
        "client_waiting_hours": 0.2,
    },
    name="row_figures",
    weight=6.0,
)
