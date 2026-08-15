"""Diagnostic checks for the WIP review."""

import rewardkit as rk

D = "wip_review.json"
rk.schema_ok(D, name="deliverable_schema", weight=1.0)
rk.ordered(D, name="sorted_rows", weight=1.0)
