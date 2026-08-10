"""Canonical answer criteria for billing-hygiene-audit."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)

DELIVERABLE = "hygiene.json"
ANOMALOUS_DAY_FIELDS = (
    "date",
    "timekeeper",
    "entry_ids",
    "matter_numbers",
    "minutes",
    "billed_cents",
)
REQUIRED_FIELDS = [
    "entries_reviewed",
    "timekeepers_reviewed",
    "anomalous_timekeeper_days",
    "anomalous_entry_count",
    "anomalous_minutes_total",
    "anomalous_billed_cents_total",
    "phantom_note_ids",
]

rk.numeric_close(
    DELIVERABLE,
    "entries_reviewed",
    TRUTH["entries_reviewed"],
    name="entries_reviewed",
    weight=2.0,
)
rk.numeric_close(
    DELIVERABLE,
    "timekeepers_reviewed",
    TRUTH["timekeepers_reviewed"],
    name="timekeepers_reviewed",
    weight=2.0,
)
rk.set_f1(
    DELIVERABLE,
    "anomalous_timekeeper_days",
    TRUTH["anomalous_timekeeper_days"],
    fields=ANOMALOUS_DAY_FIELDS,
    name="anomalous_days.f1",
    weight=59.4,
)
rk.exact_set(
    DELIVERABLE,
    "anomalous_timekeeper_days",
    TRUTH["anomalous_timekeeper_days"],
    fields=ANOMALOUS_DAY_FIELDS,
    name="anomalous_days.certified",
    weight=6.6,
)
rk.numeric_close(
    DELIVERABLE,
    "anomalous_entry_count",
    TRUTH["anomalous_entry_count"],
    name="anomalous_entry_count",
    weight=3.0,
)
rk.numeric_close(
    DELIVERABLE,
    "anomalous_minutes_total",
    TRUTH["anomalous_minutes_total"],
    name="anomalous_minutes_total",
    weight=4.0,
)
rk.numeric_close(
    DELIVERABLE,
    "anomalous_billed_cents_total",
    TRUTH["anomalous_billed_cents_total"],
    name="anomalous_billed_cents_total",
    weight=4.0,
)
rk.set_f1(
    DELIVERABLE,
    "phantom_note_ids",
    TRUTH["phantom_note_ids"],
    name="phantom_notes.f1",
    weight=9.0,
)
rk.exact_set(
    DELIVERABLE,
    "phantom_note_ids",
    TRUTH["phantom_note_ids"],
    name="phantom_notes.certified",
    weight=1.0,
)
rk.has_fields(
    DELIVERABLE,
    REQUIRED_FIELDS,
    name="deliverable_format",
    weight=9.0,
)
