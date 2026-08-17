"""Process criteria: the deliverable exists and has the right shape."""

import rewardkit as rk

rk.schema_ok("open_items.json", name="deliverable_schema", weight=1.0)
