"""Diagnostic (non-reward) checks for the status-integrity review."""

import rewardkit as rk

rk.schema_ok("status_integrity.json", name="deliverable_schema", weight=1.0)
