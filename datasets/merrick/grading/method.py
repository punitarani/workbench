"""Process criteria: the deliverable exists and has the shape asked for.

Separate from the answer dimension so a run that produced nothing readable
is distinguishable in the trial log from one that produced a register and
got it wrong. Those are different failures and the first is usually a
harness problem rather than a model one.
"""

import criteria
import rewardkit as rk

rk.schema_ok(criteria.DELIVERABLE, name="deliverable_schema", weight=1.0)
