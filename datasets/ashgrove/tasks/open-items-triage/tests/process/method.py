"""Diagnostic (non-reward) checks for open-items triage."""

from pathlib import Path

import rewardkit as rk

D = "open_items.json"
rk.schema_ok(D, name="deliverable_schema", weight=1.0)
rk.ordered(D, name="sorted_by_thread", weight=1.0)
