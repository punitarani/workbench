"""Canonical answer criteria for visitor-log-audit."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)

DELIVERABLE = "visitor-log.json"
BREACH_FIELDS = ("ts", "date", "asked_by", "asked_of", "resolution")
REQUIRED_FIELDS = [
    "requests_reviewed",
    "conversations_reviewed",
    "same_day_breach_ts",
    "same_day_breaches",
    "returned_same_day",
    "returned_next_working_day_ts",
    "unresolved_ts",
]

rk.numeric_close(
    DELIVERABLE,
    "requests_reviewed",
    TRUTH["requests_reviewed"],
    name="requests_reviewed",
    weight=2.0,
)
rk.numeric_close(
    DELIVERABLE,
    "conversations_reviewed",
    TRUTH["conversations_reviewed"],
    name="conversations_reviewed",
    weight=2.0,
)
rk.set_f1(
    DELIVERABLE,
    "same_day_breach_ts",
    TRUTH["same_day_breach_ts"],
    name="breach_ts.f1",
    weight=26.1,
)
rk.exact_set(
    DELIVERABLE,
    "same_day_breach_ts",
    TRUTH["same_day_breach_ts"],
    name="breach_ts.certified",
    weight=2.9,
)
rk.set_f1(
    DELIVERABLE,
    "same_day_breaches",
    TRUTH["same_day_breaches"],
    fields=BREACH_FIELDS,
    name="breaches.f1",
    weight=27.0,
)
rk.exact_set(
    DELIVERABLE,
    "same_day_breaches",
    TRUTH["same_day_breaches"],
    fields=BREACH_FIELDS,
    name="breaches.certified",
    weight=3.0,
)
rk.numeric_close(
    DELIVERABLE,
    "returned_same_day",
    TRUTH["returned_same_day"],
    name="returned_same_day",
    weight=5.0,
)
rk.set_f1(
    DELIVERABLE,
    "returned_next_working_day_ts",
    TRUTH["returned_next_working_day_ts"],
    name="next_working_day.f1",
    weight=13.5,
)
rk.exact_set(
    DELIVERABLE,
    "returned_next_working_day_ts",
    TRUTH["returned_next_working_day_ts"],
    name="next_working_day.certified",
    weight=1.5,
)
rk.set_f1(
    DELIVERABLE,
    "unresolved_ts",
    TRUTH["unresolved_ts"],
    name="unresolved.f1",
    weight=7.2,
)
rk.exact_set(
    DELIVERABLE,
    "unresolved_ts",
    TRUTH["unresolved_ts"],
    name="unresolved.certified",
    weight=0.8,
)
rk.exact_schema(
    DELIVERABLE,
    REQUIRED_FIELDS,
    "same_day_breaches",
    BREACH_FIELDS,
    name="deliverable_format",
    weight=9.0,
)
