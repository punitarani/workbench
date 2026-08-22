"""Grading for the live commitment register: three counts and the rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

**`KEY` carries the day, and that is the whole design.** A commitment is
identified by who owes it, on what, and by when: "Cecile committed to
Friday" and "Cecile committed to Thursday" are two different commitments,
one of which is dead. Reporting the superseded one is a false positive
rather than a wrong field, which is both semantically right and what makes
the arithmetic work. Measured through this module's own comparisons on a
six-month record, against a register built by a reader who takes the first
mention and stops:

    keyed (matter, owner), day a field   row_f1 1.000  row_facts 0.584
    keyed (matter, owner, day)           row_f1 0.757  row_facts 0.168

`row_facts` collapses rather than degrading because a wrong key means the
row is not matched at all — every field on it misses, and the invented row
draws `row_fields`' extra-row penalty on top.

**A key that can collapse two real rows would cap the ceiling invisibly.**
Both sides dedupe identically, so row F1 still reads 1.000 and the loss
shows only in the per-row check. The brief admits **one live commitment per
person per matter**, so `(matter, owner)` alone already names a row; the day
rides in the key for the reason above, and cannot introduce a collision it
does not already have. `checks/verify.py` asserts the row count before and
after keying.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's grading
# that its criteria cannot derive from the oracle.
DELIVERABLE = "live_commitments.json"

# The list in the deliverable that carries one entry per live commitment.
ROWS = "live"

# Who owes it, on what, and by when.
KEY = ("matter", "owner", "day")

# What is left once the key has taken three of the five fields. Both are
# strings the record states outright -- a meeting id and its start -- so
# exact is the only defensible tolerance; anything else would be
# decoration.
#
# They are graded rather than dropped because they are the *evidence*: a
# register that names the right day and cannot say which room it was said
# in has not been read, it has been guessed, and the two are
# indistinguishable in a `day` field with five possible values.
FIELDS: dict[str, float] = {"meeting_id": 0.0, "said_at": 0.0}

# Counts that are a tally of the rows this grading already checks. Paying
# for them again does not add signal, it multiplies the signal already
# there -- and it raises the floor, because an answer whose rows are wrong
# can still tally its own wrong rows correctly. They move to the process
# dimension, where a reader who cannot add up their own register is still
# visible.
DERIVED_FROM_ROWS = ("distinct_owners", "matters_with_a_commitment")

# Nothing here is restated by the brief. The window's dates are prose, but
# the report does not ask for them back -- an earlier task in this dataset
# was handing away 10% of its reward that way.
RESTATED_FROM_BRIEF: tuple[str, ...] = ()

# What survives as an independently graded scalar, and why each earns it:
#
#   meetings_read      how much of the window was opened. Nothing else
#                      captures it, and it is the one number a reader who
#                      sampled cannot fake from the rows they found.
#   turns_read         the same, one level down. A reader who opened every
#                      meeting and skimmed each is visible here and
#                      nowhere else.
#   superseded_count   how many commitments were found and discarded. This
#                      is the only figure in the report that a
#                      first-answer reader gets *structurally* wrong: they
#                      never saw a supersession, so they report zero. It is
#                      not derivable from `live`, because the rows are
#                      precisely what supersession removed.
