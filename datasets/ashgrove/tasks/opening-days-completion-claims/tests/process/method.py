"""Process criteria: the deliverable exists and has the right shape."""

import rewardkit as rk

rk.schema_ok("opening_claims.json", name="deliverable_schema", weight=1.0)
