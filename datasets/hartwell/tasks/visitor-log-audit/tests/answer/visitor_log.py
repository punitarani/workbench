"""Canonical answer criteria for visitor-log-audit."""

import json
from pathlib import Path

import rewardkit as rk

TRUTH = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())

DELIVERABLE = "visitor-log.json"
BREACH_FIELDS = ("ts", "date", "asked_by", "asked_of", "resolution")
CUSTODY_FIELDS = (
    "request_ts",
    "request_date",
    "asked_by",
    "asked_of",
    "first_return_surface",
    "first_return_id",
    "first_return_at",
    "outcome",
)

for key in (
    "requests_reviewed",
    "conversations_reviewed",
    "returned_same_day",
    "returned_next_working_day",
    "unresolved_by_followup",
):
    rk.numeric_close(
        DELIVERABLE,
        key,
        TRUTH[key],
        name=key,
        weight=1.0,
    )

for key, weight, fields, name in (
    ("same_day_breach_ts", 4.0, None, "breach_ts"),
    ("same_day_breaches", 4.0, BREACH_FIELDS, "breaches"),
    ("returned_next_working_day_ts", 3.0, None, "next_working_day"),
    ("unresolved_ts", 2.0, None, "unresolved"),
):
    rk.set_f1(
        DELIVERABLE,
        key,
        TRUTH[key],
        fields=fields,
        name=f"{name}.f1",
        weight=weight * 0.9,
    )
    rk.exact_set(
        DELIVERABLE,
        key,
        TRUTH[key],
        fields=fields,
        name=f"{name}.certified",
        weight=weight * 0.1,
    )

rk.set_f1(
    DELIVERABLE,
    "custody_audit",
    TRUTH["custody_audit"],
    fields=CUSTODY_FIELDS,
    name="custody_audit.f1",
    weight=65.7,
)
rk.exact_set(
    DELIVERABLE,
    "custody_audit",
    TRUTH["custody_audit"],
    fields=CUSTODY_FIELDS,
    name="custody_audit.certified",
    weight=7.3,
)
rk.custody_audit_reconciles(
    DELIVERABLE,
    name="custody_audit_reconciles",
    weight=6.0,
)
rk.exact_schema(
    DELIVERABLE,
    name="deliverable_format",
    weight=3.0,
)
