"""Answer criteria for the status-integrity review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "status_integrity.json"

rk.scalar(
    D, "engagements_reviewed", T["engagements_reviewed"], name="reviewed", weight=1.0
)
rk.scalar(D, "dormant_count", T["dormant_count"], name="dormant", weight=2.0)
rk.scalar(
    D,
    "worked_after_close_count",
    T["worked_after_close_count"],
    name="after_close",
    weight=2.0,
)
rk.scalar(D, "churned_count", T["churned_count"], name="churned", weight=2.0)
rk.flagged_f1(D, T["flagged"], name="flagged.f1", weight=3.0)
rk.row_fields(
    D,
    T["flagged"],
    ["status", "hours_logged", "dormant", "worked_after_close", "status_changes"],
    name="row_flags",
    weight=5.0,
)
