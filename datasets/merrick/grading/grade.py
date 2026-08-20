"""Register this task's answer criteria — the step that was missing entirely.

Every task in this dataset shipped a `criteria.py` naming its rows, its row
key and its graded fields, and a `criteria_base.py` holding the criterion
bodies behind `@criterion(shared=True)`. **Nothing ever called them.**

Declaring a criterion and registering one are different acts. The decorator
makes `rk.row_f1(...)` available; something has to invoke it with this
task's oracle before Reward Kit has a reward to compute. Run against the
real discovery, a task with only declarations returns **zero** rewards,
and Reward Kit writes `{}` — so every trial of every model would have come
back with no score at all, for reasons no model had any part in.

This file is generic on purpose. It reads the constants out of the task's
own `criteria.py` and the values out of its `oracle.json`, so one copy
serves every task and a task cannot drift from its own grader by being
edited in one place and not the other.

**Weights.** The row set carries the most because it is the task: which rows
belong in the register. Per-row facts carry less because they are only
reachable once the row is right. Scalars carry least individually, but there
are several and together they catch a reader who found the rows and
miscounted what they read — which is a different failure and worth seeing
separately in the trial log.
"""

import json
from pathlib import Path

import criteria
import rewardkit as rk

_TESTS = Path(__file__).resolve().parent.parent
ORACLE = json.loads((_TESTS / "oracle.json").read_text(encoding="utf-8"))

# The deliverable's name is the one thing not derivable from the criteria, so
# it is read from the task's own manifest rather than guessed from the rows.
DELIVERABLE = criteria.DELIVERABLE

ROWS = criteria.ROWS
KEY = list(criteria.KEY)
FIELDS = dict(criteria.FIELDS)

# Everything at the top level that is not the row list. These are the counts
# a reader reports about the work rather than the work itself.
_SCALARS = sorted(k for k, v in ORACLE.items() if not isinstance(v, list))

for _name in _SCALARS:
    rk.scalar(DELIVERABLE, _name, ORACLE[_name], 0, name=_name, weight=1.0)

# The row set. Five is not a round number: it is what makes one missing row
# cost more than one wrong field on a row that is present, which is the
# ordering this dataset's briefs promise their readers.
rk.row_f1(
    DELIVERABLE,
    ROWS,
    KEY,
    ORACLE[ROWS],
    name=f"{ROWS}.f1",
    weight=5.0,
)

rk.row_fields(
    DELIVERABLE,
    ROWS,
    KEY,
    ORACLE[ROWS],
    FIELDS,
    name="row_facts",
    weight=3.0,
)
