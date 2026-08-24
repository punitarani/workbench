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

# Three of this task's six figures are tallies of the rows it already
# grades: `hits_total` is len(hits), `distinct_authors` is the number of
# distinct `author` values on them, and `top_author` is their mode. Paying
# for those does not add signal, it multiplies the signal already there --
# and it raises the floor, because an answer whose rows are wrong can still
# tally its own wrong rows correctly. Measured: an EMPTY register with the
# scalars right scored 0.429 on the real grading path, inside the 0.2-0.8
# band with no rows at all.
#
# They move to the process dimension, where a reader who cannot add up
# their own register is still visible, and stop being paid twice.
DERIVED_FROM_ROWS = ("hits_total", "distinct_authors", "top_author")

# Every graded row field is a string the record states outright -- a name,
# a date, a subject line, a channel name. Exact is the only defensible
# tolerance for any of them; a tolerance here would be decoration.
FIELDS: dict[str, float] = {"author": 0.0, "sent_date": 0.0, "where": 0.0}
