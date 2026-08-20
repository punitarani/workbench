"""Grading for the search-term hit report: totals, two objects, and rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

`KEY` is the message's own ref, and the instruction admits **one row per
message** — so a ref names exactly one row on both sides. A key that
collapses two rows caps the ceiling below 1.0 for reasons no agent can fix,
and row F1 will not show it: both sides dedupe identically and it still
reads 1.000. Assert the row count before and after keying.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's
# grading that its criteria cannot derive from the oracle.
DELIVERABLE = "word_register.json"

# The list in the deliverable that carries one entry per matching message.
ROWS = "hits"
# One row per message; the message's own id names it.
KEY = ("ref",)
# Every graded row field is a string the record states outright -- a name,
# a date, a subject line, a channel name. Exact is the only defensible
# tolerance for any of them; a tolerance here would be decoration.
FIELDS: dict[str, float] = {"author": 0.0, "sent_date": 0.0, "where": 0.0}
