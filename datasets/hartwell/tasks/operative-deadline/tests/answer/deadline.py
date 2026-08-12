"""Answer criteria for operative-deadline."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads(
    (Path(__file__).resolve().parent.parent / "ground_truth.json").read_text()
)
ORACLE = json.loads(
    (Path(__file__).resolve().parent.parent / "oracle.json").read_text()
)
D = "deadline.json"
# Named, so reward-details.json can say which field failed rather than
# reporting two criteria under one auto-name.
# The headline answers are one search away once the correction is found,
# and every measured cell that found it got all of them. They stay worth
# reporting, but a task whose score is 39% conclusions is a task that
# rewards answering the question instead of doing the work -- the two
# screens that actually separated models paid for a sourced ledger and
# left a model that nailed both headlines under 0.30.
rk.field_equals(
    D, "operative_date", T["operative_date"], name="operative_date", weight=6.0
)
rk.field_prefix_any(
    D,
    "operative_time",
    T["operative_time_prefixes"],
    name="operative_time",
    weight=2.0,
)
rk.field_prefix_any(
    D,
    "correction_ts",
    [T["correction_ts_prefix"]],
    name="correction_ts",
    weight=4.0,
)
rk.ordered_similarity(
    D,
    "superseded_dates",
    T["superseded_dates"],
    name="superseded_dates",
    weight=5.0,
)
rk.supersession_f1(D, T["supersessions"], name="supersessions.f1", weight=5.0)
rk.supersession_exact(D, T["supersessions"], name="supersessions.certified", weight=1.0)
# The notice audit is the work product and carries the score. The stale
# list is a partition of it, so it keeps only the weight of a summary:
# when it was 56% of the task, answering it was the task, and a
# precision-1.0 under-claim of two or three items scored well.
rk.notice_audit_f1(D, ORACLE["notice_audit"], name="notice_audit.f1", weight=55.0)
rk.notice_audit_exact(
    D, ORACLE["notice_audit"], name="notice_audit.certified", weight=7.0
)
rk.notice_audit_reconciles(D, name="notice_audit_reconciles", weight=5.0)
rk.reference_f1(D, T["stale_calendar_refs"], name="stale_calendar_refs.f1", weight=3.0)
rk.reference_exact(
    D, T["stale_calendar_refs"], name="stale_calendar_refs.certified", weight=1.0
)
rk.exact_schema(D, name="deliverable_format", weight=6.0)
