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

# ...except the ones the brief hands the agent.
#
# `window_end` is the boundary the instruction states in its own prose --
# "on or before Thursday 19 February 2026" -- and the skeleton asks for it
# back as a date. Graded here it was **10% of the reward on every task in
# this dataset**, obtainable by transcribing one sentence of the prompt.
# Measured on a register with three rows: an answer with the row list empty
# and the scalars right scored 0.2, and a frontier model reformatting a
# date it was given scored 0.1 for no work at all.
#
# That is not a small thing when the target band is 0.2-0.8. A floor of 0.1
# is a tenth of the range spent before the task starts.
#
# `criteria_base` already states the principle this restores: presentation
# and process checks belong in a dimension that informs without moving the
# number. These move to `method.py`, where they still catch a reader who
# windowed on the wrong day -- they just stop paying for it.
_RESTATED = frozenset(getattr(criteria, "RESTATED_FROM_BRIEF", ()))

# ...and the ones that are already inside the row set.
#
# A register that reports its rows and then also reports counts *of* those
# rows is grading one piece of work twice. On the off-sense register six
# scalars carried 43% of the reward and five of them —  `hits_total`,
# `distinct_authors`, `top_author`, `form_counts`, `department_counts` —
# are each a tally over `hits`, which `row_f1` and `row_fields` already
# grade. Only the count of what was *read* is independent: it measures how
# much of the window the reader opened, and nothing else captures that.
#
# Paying for a derived figure does not add signal, it multiplies the
# signal already there — and it raises the floor, because an answer that
# gets the rows badly wrong can still tally its own wrong rows correctly.
# Checked in `process`, where a reader who cannot add up their own
# register is still visible.
_DERIVED = frozenset(getattr(criteria, "DERIVED_FROM_ROWS", ()))

for _name in _SCALARS:
    if _name in _RESTATED or _name in _DERIVED:
        continue
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
