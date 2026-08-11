"""Canonical answer criteria for billing-hygiene-audit."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())

DELIVERABLE = "hygiene.json"
ANOMALOUS_DAY_FIELDS = (
    "date",
    "timekeeper",
    "entry_ids",
    "matter_numbers",
    "minutes",
    "billed_cents",
)
DAILY_REVIEW_FIELDS = (
    "date",
    "timekeeper",
    "billable_entry_ids",
    "sent_gmail_ids",
    "sent_slack_ts",
    "corroborated_entry_ids",
    "corroborated_matter_numbers",
    "disposition",
)

for key in (
    "entries_reviewed",
    "timekeepers_reviewed",
    "person_days_reviewed",
    "cleared_by_communication",
    "cleared_no_corroboration",
    "anomalous_timekeeper_day_count",
    "anomalous_entry_count",
    "anomalous_minutes_total",
    "anomalous_billed_cents_total",
):
    rk.numeric_close(
        DELIVERABLE,
        key,
        TRUTH[key],
        name=key,
        weight=1.0,
    )

rk.set_f1(
    DELIVERABLE,
    "anomalous_timekeeper_days",
    TRUTH["anomalous_timekeeper_days"],
    fields=ANOMALOUS_DAY_FIELDS,
    name="anomalous_days.f1",
    weight=5.4,
)
rk.exact_set(
    DELIVERABLE,
    "anomalous_timekeeper_days",
    TRUTH["anomalous_timekeeper_days"],
    fields=ANOMALOUS_DAY_FIELDS,
    name="anomalous_days.certified",
    weight=0.6,
)
rk.set_f1(
    DELIVERABLE,
    "phantom_note_ids",
    TRUTH["phantom_note_ids"],
    name="phantom_notes.f1",
    weight=3.6,
)
rk.exact_set(
    DELIVERABLE,
    "phantom_note_ids",
    TRUTH["phantom_note_ids"],
    name="phantom_notes.certified",
    weight=0.4,
)
rk.set_f1(
    DELIVERABLE,
    "daily_review",
    TRUTH["daily_review"],
    fields=DAILY_REVIEW_FIELDS,
    name="daily_review.f1",
    weight=64.8,
)
rk.exact_set(
    DELIVERABLE,
    "daily_review",
    TRUTH["daily_review"],
    fields=DAILY_REVIEW_FIELDS,
    name="daily_review.certified",
    weight=7.2,
)
rk.daily_review_reconciles(
    DELIVERABLE,
    name="daily_review_reconciles",
    weight=6.0,
)
rk.exact_schema(
    DELIVERABLE,
    name="deliverable_format",
    weight=3.0,
)
