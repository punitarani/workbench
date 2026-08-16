"""Diagnostic (non-reward) checks for the follow-through review."""

import rewardkit as rk

rk.schema_ok("follow_through.json", name="deliverable_schema", weight=1.0)
