"""Canonical answer criteria for the Meridian fee reconstruction."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)

DELIVERABLE = "dispute.json"
ENTRY_FIELDS = ("id", "date", "minutes")
UNSUPPORTED_DAY_FIELDS = (
    "date",
    "entry_ids",
    "entry_count",
    "minutes",
    "billed_cents",
)
REQUIRED_FIELDS = [
    "cutoff_date",
    "total_minutes",
    "entry_count",
    "entries",
    "minutes_by_timekeeper",
    "timekeepers",
    "challenged_by",
    "challenge_date",
    "unsupported_days",
]

rk.field_equals(
    DELIVERABLE,
    "cutoff_date",
    TRUTH["cutoff_date"],
    name="cutoff_date",
    weight=3.0,
)
rk.numeric_close(
    DELIVERABLE,
    "total_minutes",
    TRUTH["total_minutes"],
    name="total_minutes",
    weight=5.0,
)
rk.numeric_close(
    DELIVERABLE,
    "entry_count",
    TRUTH["entry_count"],
    name="entry_count",
    weight=3.0,
)
rk.set_f1(
    DELIVERABLE,
    "entries",
    TRUTH["entries"],
    fields=ENTRY_FIELDS,
    name="disputed_entries.f1",
    weight=10.8,
)
rk.exact_set(
    DELIVERABLE,
    "entries",
    TRUTH["entries"],
    fields=ENTRY_FIELDS,
    name="disputed_entries.certified",
    weight=1.2,
)
rk.marker_map_f1(
    DELIVERABLE,
    "minutes_by_timekeeper",
    TRUTH["minutes_by_timekeeper_markers"],
    name="minutes_by_timekeeper.f1",
    weight=4.5,
)
rk.exact_marker_map(
    DELIVERABLE,
    "minutes_by_timekeeper",
    TRUTH["minutes_by_timekeeper_markers"],
    name="minutes_by_timekeeper.certified",
    weight=0.5,
)
rk.marker_list_f1(
    DELIVERABLE,
    "timekeepers",
    TRUTH["timekeeper_markers"],
    name="timekeepers.f1",
    weight=1.8,
)
rk.exact_marker_list(
    DELIVERABLE,
    "timekeepers",
    TRUTH["timekeeper_markers"],
    name="timekeepers.certified",
    weight=0.2,
)
rk.field_names_any(
    DELIVERABLE,
    "challenged_by",
    TRUTH["challenged_by_markers"],
    name="challenged_by",
    weight=2.0,
)
rk.field_equals(
    DELIVERABLE,
    "challenge_date",
    TRUTH["challenge_date"],
    name="challenge_date",
    weight=3.0,
)
rk.set_f1(
    DELIVERABLE,
    "unsupported_days",
    TRUTH["unsupported_days"],
    fields=UNSUPPORTED_DAY_FIELDS,
    name="unsupported_days.f1",
    weight=50.4,
)
rk.exact_set(
    DELIVERABLE,
    "unsupported_days",
    TRUTH["unsupported_days"],
    fields=UNSUPPORTED_DAY_FIELDS,
    name="unsupported_days.certified",
    weight=5.6,
)
rk.has_fields(
    DELIVERABLE,
    REQUIRED_FIELDS,
    name="deliverable_format",
    weight=9.0,
)
