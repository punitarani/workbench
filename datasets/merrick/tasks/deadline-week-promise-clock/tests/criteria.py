"""Grading for the deadline-week promise clock. The shape lives in
`criteria_base`; this names the task's own rows, its row key, and the
tolerance on each field.

`KEY` is a pair because a row is a message *and* a due date. The brief
gives a message saying `by Friday` and `EOD` two rows, so keyed on `ref`
alone the two collapse into one and the ceiling drops below 1.0 for a
reason no agent can fix. It does not show in row F1 either — both sides
dedupe identically and it still reads 1.000. `verify.py` asserts the row
count before and after keying, which is where it does show.

`due_date` is graded by the key rather than by `FIELDS`: a wrong date is a
row the truth does not contain, and it should cost F1 rather than one
field of one row.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable that carries one entry per resolved promise.
ROWS = "promises"
# The fields that together name exactly one row.
KEY = ("ref", "due_date")
# Per-field tolerance. Every field here is exact: two dates and a name are
# either right or wrong, and `followed_up` is a boolean, which
# `criteria_base._matches` tests before it reaches any tolerance at all.
FIELDS: dict[str, float] = {
    "author": 0.0,
    "sent_date": 0.0,
    "followed_up": 0.0,
}
