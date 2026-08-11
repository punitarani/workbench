"""Canonical answer criteria for the Meridian fee reconstruction."""

import json
from pathlib import Path

import rewardkit as rk

TESTS = Path(__file__).resolve().parent.parent
TRUTH = json.loads((TESTS / "oracle.json").read_text())
MARKERS = json.loads((TESTS / "ground_truth.json").read_text())

DELIVERABLE = "dispute.json"
ENTRY_FIELDS = ("id", "date", "minutes")
UNSUPPORTED_DAY_FIELDS = (
    "date",
    "entry_ids",
    "entry_count",
    "minutes",
    "billed_cents",
)
SUPPORT_AUDIT_FIELDS = (
    "date",
    "entry_ids",
    "entry_count",
    "minutes",
    "billed_cents",
    "gmail_message_ids",
    "slack_message_ts",
    "supported",
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
    "support_audit",
    "unsupported_days",
]

rk.field_equals(
    DELIVERABLE,
    "cutoff_date",
    TRUTH["cutoff_date"],
    name="cutoff_date",
    weight=2.0,
)
rk.numeric_close(
    DELIVERABLE,
    "total_minutes",
    TRUTH["total_minutes"],
    name="total_minutes",
    weight=2.0,
)
rk.numeric_close(
    DELIVERABLE,
    "entry_count",
    TRUTH["entry_count"],
    name="entry_count",
    weight=1.0,
)
rk.set_f1(
    DELIVERABLE,
    "entries",
    TRUTH["entries"],
    fields=ENTRY_FIELDS,
    name="disputed_entries.f1",
    weight=7.2,
)
rk.exact_set(
    DELIVERABLE,
    "entries",
    TRUTH["entries"],
    fields=ENTRY_FIELDS,
    name="disputed_entries.certified",
    weight=0.8,
)
rk.marker_map_f1(
    DELIVERABLE,
    "minutes_by_timekeeper",
    MARKERS["minutes_by_timekeeper_markers"],
    name="minutes_by_timekeeper.f1",
    weight=2.7,
)
rk.exact_marker_map(
    DELIVERABLE,
    "minutes_by_timekeeper",
    MARKERS["minutes_by_timekeeper_markers"],
    name="minutes_by_timekeeper.certified",
    weight=0.3,
)
rk.marker_list_f1(
    DELIVERABLE,
    "timekeepers",
    MARKERS["timekeeper_markers"],
    name="timekeepers.f1",
    weight=0.9,
)
rk.exact_marker_list(
    DELIVERABLE,
    "timekeepers",
    MARKERS["timekeeper_markers"],
    name="timekeepers.certified",
    weight=0.1,
)
rk.field_names_any(
    DELIVERABLE,
    "challenged_by",
    MARKERS["challenged_by_markers"],
    name="challenged_by",
    weight=1.0,
)
rk.field_equals(
    DELIVERABLE,
    "challenge_date",
    TRUTH["challenge_date"],
    name="challenge_date",
    weight=2.0,
)
rk.set_f1(
    DELIVERABLE,
    "support_audit",
    TRUTH["support_audit"],
    fields=SUPPORT_AUDIT_FIELDS,
    name="support_audit.f1",
    weight=48.6,
)
rk.exact_set(
    DELIVERABLE,
    "support_audit",
    TRUTH["support_audit"],
    fields=SUPPORT_AUDIT_FIELDS,
    name="support_audit.certified",
    weight=5.4,
)
rk.set_f1(
    DELIVERABLE,
    "unsupported_days",
    TRUTH["unsupported_days"],
    fields=UNSUPPORTED_DAY_FIELDS,
    name="unsupported_days.f1",
    weight=18.0,
)
rk.exact_set(
    DELIVERABLE,
    "unsupported_days",
    TRUTH["unsupported_days"],
    fields=UNSUPPORTED_DAY_FIELDS,
    name="unsupported_days.certified",
    weight=2.0,
)
rk.has_fields(
    DELIVERABLE,
    REQUIRED_FIELDS,
    name="deliverable_format",
    weight=6.0,
)
