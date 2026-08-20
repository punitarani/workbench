"""Grading for the unanswered-question register.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

`KEY` is the message id alone. The rule admits at most one row per message
however many question marks the body carries, so a message names exactly one
row on both sides. Keying on thread instead would collapse the several
unanswered questions a long thread can hold, and row F1 would not show it --
both sides dedupe identically and it still reads 1.000.

`addressees` is a list and is graded by exact sequence, which is why the
brief fixes the order to alphabetical. Left free, a correct set written in a
different order scores zero on a field the agent got right.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's
# grading that its criteria cannot derive from the oracle.
DELIVERABLE = "unanswered.json"

# The list in the deliverable carrying one entry per unanswered question.
ROWS = "unanswered"
KEY = ("message_ref",)
# Asker, date and subject are strings the record states outright; addressees
# is an ordered list of names. Exact is the only defensible tolerance for any
# of them -- a tolerance here would only mask a misread recipient list, which
# is one of the two things this task is actually testing.
FIELDS: dict[str, float] = {
    "asker": 0.0,
    "asked_date": 0.0,
    "subject": 0.0,
    "addressees": 0.0,
}
