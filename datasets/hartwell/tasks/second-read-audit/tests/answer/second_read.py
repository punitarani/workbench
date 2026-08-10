"""Answer criteria for second-read-audit."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
D = "second-read.json"
rk.field_equals(D, "requests_reviewed", T["requests_reviewed"], weight=2.0)
rk.field_equals(D, "conversations_reviewed", T["conversations_reviewed"], weight=2.0)
rk.timestamp_f1(
    D,
    "unanswered_request_ts",
    T["unanswered_request_ts_prefixes"],
    name="unanswered_request_ts.f1",
    weight=50.4,
)
rk.timestamp_exact(
    D,
    "unanswered_request_ts",
    T["unanswered_request_ts_prefixes"],
    name="unanswered_request_ts.certified",
    weight=5.6,
)
rk.request_f1(D, T["unanswered_requests"], name="unanswered_requests.f1", weight=10.8)
rk.request_exact(
    D, T["unanswered_requests"], name="unanswered_requests.certified", weight=1.2
)
rk.field_equals(D, "answered_same_day", T["answered_same_day"], weight=5.0)
rk.timestamp_f1(
    D,
    "came_back_later",
    T["came_back_later_prefixes"],
    name="came_back_later.f1",
    weight=9.0,
)
rk.timestamp_exact(
    D,
    "came_back_later",
    T["came_back_later_prefixes"],
    name="came_back_later.certified",
    weight=1.0,
)
rk.marker_f1(D, T["asker_markers"], name="unanswered_askers.f1", weight=3.6)
rk.marker_exact(D, T["asker_markers"], name="unanswered_askers.certified", weight=0.4)
rk.exact_schema(D, name="deliverable_format", weight=9.0)
