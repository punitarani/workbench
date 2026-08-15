"""Answer criteria for open-items triage."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "open_items.json"

rk.count_matches(
    D, "threads_reviewed", T["threads_reviewed"], name="threads_reviewed", weight=1.0
)
rk.count_matches(
    D,
    "awaiting_firm_count",
    T["awaiting_firm_count"],
    name="awaiting_count",
    weight=1.0,
)
rk.count_matches(
    D,
    "closed_by_client_courtesy",
    T["closed_by_client_courtesy"],
    name="courtesy_count",
    weight=1.0,
)
rk.awaiting_f1(D, T["awaiting_firm"], name="awaiting.f1", weight=4.0)
rk.awaiting_exact(D, T["awaiting_firm"], name="awaiting.exact", weight=1.5)
rk.item_fields(D, T["awaiting_firm"], name="thread_details", weight=2.5)
