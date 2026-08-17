"""Process criteria: the deliverable exists and has the right shape."""

import rewardkit as rk

rk.schema_ok("follow_through.json", name="deliverable_schema", weight=1.0)
