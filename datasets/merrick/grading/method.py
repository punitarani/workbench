"""Process criteria: the deliverable exists and has the shape asked for.

Separate from the answer dimension so a run that produced nothing readable
is distinguishable in the trial log from one that produced a register and
got it wrong. Those are different failures and the first is usually a
harness problem rather than a model one.
"""

import json
from pathlib import Path

import criteria
import rewardkit as rk

rk.schema_ok(criteria.DELIVERABLE, name="deliverable_schema", weight=1.0)

# Scalars the brief states outright. Checked, because a reader who windowed
# on the wrong day should be visible in the trial log; unpaid, because the
# answer was in the prompt. See the note in `answer/grade.py`.
_ORACLE = json.loads(
    (Path(__file__).resolve().parent.parent / "oracle.json").read_text(encoding="utf-8")
)
for _name in sorted(frozenset(getattr(criteria, "RESTATED_FROM_BRIEF", ()))):
    if _name in _ORACLE:
        rk.scalar(
            criteria.DELIVERABLE,
            _name,
            _ORACLE[_name],
            0,
            name=_name,
            weight=1.0,
        )
