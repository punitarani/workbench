"""Diagnostic (non-reward) checks for the follow-through review."""

import rewardkit as rk

rk.schema_ok("work_product_review.json", name="deliverable_schema", weight=1.0)
