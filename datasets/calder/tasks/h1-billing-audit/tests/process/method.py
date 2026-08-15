"""Diagnostic (non-reward) coverage for h1-billing-audit."""

import json
from pathlib import Path

import rewardkit as rk

T = json.loads((Path(__file__).resolve().parent.parent / "oracle.json").read_text())
D = "h1_billing_audit.json"

rk.schema_ok(D, name="deliverable_schema", weight=1.0)
rk.total_hours(D, T["total_logged_hours"], name="total_hours", weight=1.0)
rk.ledger(D, T["matters_by_hours"], name="matter_ledger", weight=1.0)
rk.hygiene(
    D,
    T["worked_but_untimed"],
    T["untouched_matters"],
    name="hygiene_findings",
    weight=1.0,
)
rk.cam_dispute(D, T["cam_dispute"], name="cam_dispute", weight=1.0)
