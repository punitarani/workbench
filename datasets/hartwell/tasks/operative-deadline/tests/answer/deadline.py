"""Answer criteria for operative-deadline."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
D = "deadline.json"
# Named, so reward-details.json can say which field failed rather than
# reporting two criteria under one auto-name.
rk.field_equals(
    D, "operative_date", T["operative_date"], name="operative_date", weight=10.0
)
rk.field_prefix_any(
    D,
    "operative_time",
    T["operative_time_prefixes"],
    name="operative_time",
    weight=4.0,
)
rk.field_prefix_any(
    D,
    "correction_ts",
    [T["correction_ts_prefix"]],
    name="correction_ts",
    weight=7.0,
)
rk.ordered_similarity(
    D,
    "superseded_dates",
    T["superseded_dates"],
    name="superseded_dates",
    weight=8.0,
)
rk.supersession_f1(D, T["supersessions"], name="supersessions.f1", weight=9.0)
rk.supersession_exact(D, T["supersessions"], name="supersessions.certified", weight=1.0)
rk.reference_f1(D, T["stale_calendar_refs"], name="stale_calendar_refs.f1", weight=50.4)
rk.reference_exact(
    D, T["stale_calendar_refs"], name="stale_calendar_refs.certified", weight=5.6
)
rk.exact_schema(D, name="deliverable_format", weight=5.0)
