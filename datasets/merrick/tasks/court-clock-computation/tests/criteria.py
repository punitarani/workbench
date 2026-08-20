"""Grading for the court-clock register. The shape lives in `criteria_base`;
this names the task's own rows, its row key, and the tolerance on each field.

`KEY` must distinguish every real row. A collapsing key caps the ceiling
below 1.0 for reasons no agent can fix, and row F1 will not show it — both
sides dedupe identically and it still reads 1.000.

Here a row is a **message and a number of days**. Keyed on `ref` alone,
every message that names two different intervals collapses to one row, and
the grader marks half that message's work as all of it. `interval_days` is
the other half of the key rather than a graded field for the same reason
the key exists: it is what tells two rows of one body apart.

The three computed values — `raw_due_date`, `due_date` and `rolled` — are
graded as fields, so a right form read off the wrong trigger loses the
arithmetic without losing the row, and a correct count that never learned
about the weekend move loses exactly one field of three.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable that carries one entry per deadline.
ROWS = "deadlines"
# The fields that together name exactly one row: the message, and which of
# its intervals this row is.
KEY = ("ref", "interval_days")
# Per-field tolerance. Every field here is a date, a name or a boolean, so
# every tolerance is exact. A date is not a quantity and a tolerance on one
# would admit a deadline off by a day, which is the entire defect this
# register exists to catch.
FIELDS: dict[str, float] = {
    "author": 0.0,
    "sent_date": 0.0,
    "raw_due_date": 0.0,
    "due_date": 0.0,
    "rolled": 0.0,
}
