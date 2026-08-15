"""Answer criteria for the WIP review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "wip_review.json"

rk.scalar(
    D, "client_engagements", T["client_engagements"], 0, name="client_count", weight=1.0
)
rk.scalar(
    D,
    "internal_engagements",
    T["internal_engagements"],
    0,
    name="internal_count",
    weight=1.0,
)
rk.scalar(
    D,
    "total_client_wip_dollars",
    T["total_client_wip_dollars"],
    5.0,
    name="total_wip",
    weight=2.0,
)
rk.scalar(
    D,
    "blended_rate_dollars_per_hour",
    T["blended_rate_dollars_per_hour"],
    0.5,
    name="blended_rate",
    weight=1.0,
)
rk.engagement_rows(D, T["engagements"], name="engagement_rows", weight=4.0)
rk.person_rows(D, T["people"], name="person_rows", weight=4.0)
