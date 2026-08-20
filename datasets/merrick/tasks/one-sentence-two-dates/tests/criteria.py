"""Grading for the date register. The shape lives in `criteria_base`; this
names the task's own rows, its row key, and the tolerance on each field.

`KEY` must distinguish every real row. This task puts two rows in one
message whenever the message names two dates, so `("ref",)` alone would
collapse exactly the rows the task exists to measure — and row F1 would
not show it, because both sides dedupe identically and it still reads
1.000. `at` is the character position of the form, unique within a
message by construction: no two of the admitted forms can begin at the
same character, and the reference solver refuses to write an oracle where
two do.

`at` is therefore graded as part of the key rather than as a field. That
is deliberate: locating the form and resolving it to a date are two
different pieces of work, and keying on the first means a row scores on
the second only once the agent has actually found where the words are.

`due_date`, `author` and `sent_date` are exact — a date is right or it is
another date, and a tolerance on a name is meaningless. No field here is
a measured quantity, so nothing takes an epsilon.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable that carries one entry per finding.
ROWS = "dates"
# The fields that together name exactly one row.
KEY = ("ref", "at")
# Per-field tolerance. 0.0 is exact.
FIELDS: dict[str, float] = {
    "due_date": 0.0,
    "author": 0.0,
    "sent_date": 0.0,
}
