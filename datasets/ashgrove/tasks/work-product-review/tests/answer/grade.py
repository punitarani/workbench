"""Answer criteria for the follow-through review."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "follow_through.json"

rk.scalar(
    D,
    "documents_in_repository",
    T["documents_in_repository"],
    name="documents_in_repository",
    weight=1.0,
)
rk.scalar(D, "delivered_count", T["delivered_count"], name="delivered", weight=2.0)
rk.scalar(
    D,
    "internal_only_count",
    T["internal_only_count"],
    name="internal_only",
    weight=2.0,
)
rk.scalar(
    D,
    "never_attached_count",
    T["never_attached_count"],
    name="never_attached",
    weight=1.5,
)
rk.undelivered_f1(D, T["undelivered"], name="undelivered.f1", weight=3.0)
rk.row_fields(
    D,
    T["undelivered"],
    ["author", "workspace", "attached_internally"],
    name="row_facts",
    weight=5.0,
)
