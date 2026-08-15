"""Answer criteria for the client responsiveness review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "sla_report.json"

rk.scalar(D, "clients", T["clients"], 0, name="clients", weight=1.0)
rk.scalar(D, "inbound_total", T["inbound_total"], 0, name="inbound_total", weight=1.5)
rk.scalar(
    D, "unanswered_total", T["unanswered_total"], 0, name="unanswered_total", weight=1.5
)
rk.scalar(
    D,
    "firm_median_reply_hours",
    T["firm_median_reply_hours"],
    0.02,
    name="firm_median_reply_hours",
    weight=1.5,
)
rk.scalar(D, "slowest_client", T["slowest_client"], name="slowest_client", weight=1.0)
rk.row_fields(
    D,
    T["client_rows"],
    {
        "inbound": 0,
        "answered": 0,
        "unanswered_message_ids": 0,
        "median_reply_hours": 0.02,
        "longest_reply_hours": 0.02,
    },
    name="row_figures",
    weight=6.0,
)
