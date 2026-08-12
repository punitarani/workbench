"""Answer criteria for second-read-audit."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
ORACLE = json.loads(
    (Path(__file__).resolve().parent.parent / "oracle.json").read_text()
)
D = "second-read.json"
# The count criteria are named, so reward-details.json can say which count
# failed rather than reporting five criteria under one auto-name.
rk.field_equals(
    D, "requests_reviewed", T["requests_reviewed"], name="requests_reviewed", weight=1.0
)
rk.field_equals(
    D,
    "conversations_reviewed",
    T["conversations_reviewed"],
    name="conversations_reviewed",
    weight=1.0,
)
rk.timestamp_f1(
    D,
    "unanswered_request_ts",
    T["unanswered_request_ts_prefixes"],
    name="unanswered_request_ts.f1",
    weight=4.5,
)
rk.timestamp_exact(
    D,
    "unanswered_request_ts",
    T["unanswered_request_ts_prefixes"],
    name="unanswered_request_ts.certified",
    weight=0.5,
)
rk.request_f1(D, T["unanswered_requests"], name="unanswered_requests.f1", weight=3.6)
rk.request_exact(
    D, T["unanswered_requests"], name="unanswered_requests.certified", weight=0.4
)
rk.field_equals(
    D,
    "answered_same_day",
    T["answered_same_day"],
    name="answered_same_day",
    weight=1.0,
)
rk.field_equals(
    D,
    "answered_next_working_day",
    ORACLE["answered_next_working_day"],
    name="answered_next_working_day",
    weight=1.0,
)
rk.field_equals(
    D,
    "unanswered_by_deadline",
    ORACLE["unanswered_by_deadline"],
    name="unanswered_by_deadline",
    weight=1.0,
)
rk.timestamp_f1(
    D,
    "came_back_later",
    T["came_back_later_prefixes"],
    name="came_back_later.f1",
    weight=2.7,
)
rk.timestamp_exact(
    D,
    "came_back_later",
    T["came_back_later_prefixes"],
    name="came_back_later.certified",
    weight=0.3,
)
rk.marker_f1(D, T["asker_markers"], name="unanswered_askers.f1", weight=1.8)
rk.marker_exact(D, T["asker_markers"], name="unanswered_askers.certified", weight=0.2)
rk.response_audit_f1(D, ORACLE["response_audit"], name="response_audit.f1", weight=64.8)
rk.response_audit_exact(
    D, ORACLE["response_audit"], name="response_audit.certified", weight=7.2
)
rk.response_audit_reconciles(D, name="response_audit_reconciles", weight=6.0)
rk.exact_schema(D, name="deliverable_format", weight=3.0)
