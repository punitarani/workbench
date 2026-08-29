"""Grading for the assignment register: two counts and the rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

**The owner is not the speaker, and that is the whole design.** Every other
register in this tree keys on the person who said the words. This one keys
on the person they were talking about, so a reader who finds every turn and
keys it on the speaker scores zero on the row set while having done all the
reading. That is the failure this family exists to separate from an honest
miss.

**`KEY` carries all three chain facts.** Who was told, in which standing
meeting, by when, from when, and over how many earlier instructions. Both
ends of the chain and its length: a reader who finds the last statement has
`due` and neither of the others, and one who finds the first has `first_due`
and neither of the others. None of the three is derivable from the other
two, and no system in this world records any of them.

At a per-statement accuracy of `a`, a row needing `k` statements is right
with probability `a**k` -- which is the only lever measured on this tree
that moves a frontier model off ceiling. Adding rows that each turn on a
single extraction does not, because row F1 is per-row.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

DELIVERABLE = "assignment_slippage.json"

ROWS = "assignments"

# Who was told, in which standing meeting, by when, and how many times
# that date was pushed LATER.
#
# `slips` is what separates this from its sibling. That one needs the
# chain's ENDS -- the last statement for `due`, the first for `first_due`,
# the room count for `superseded`. Neither needs the dates in between. A
# slip compares two consecutive resolved dates, so every link has to be
# read AND resolved against its own meeting.
KEY = ("owner", "meeting", "due", "first_due", "slips")

# What is left once the key has taken five of the seven fields. Both are
# strings the record states outright -- a meeting id and its start -- so
# exact is the only defensible tolerance.
#
# They are graded rather than dropped because they are the *evidence*: a
# register that names the right dates and cannot say which room they were
# said in has been reconstructed rather than read.
FIELDS: dict[str, float] = {"meeting_id": 0.0, "said_at": 0.0}

# Tallies of the rows this grading already checks. Paying for them again
# multiplies the signal already there and raises the floor, because an
# answer whose rows are wrong can still count its own wrong rows correctly.
# They move to the process dimension, where a reader who cannot add up
# their own register is still visible.
# `superseded_count` is NOT here, and the sibling register has it. There
# the rows carry `superseded`, so the global count is a tally of figures
# already graded and paying for it twice raises the floor. Here the rows
# carry `slips`, which is a different quantity -- a date moved later, not a
# date replaced -- so the count of what was discarded is not derivable from
# the register at all and earns its own criterion.
# The census counts move here and stop paying.
#
# Two reasons that arrive at the same place. A practitioner reviewing this
# family called them audit fields no partner wants, in a deliverable that
# should read as a table -- correct. And measured, every tier of every
# model got them identically WRONG on this world: 391 meetings and 2,037
# turns against a true 383 and 1,989, because the brief defines a standing
# series by the DAYS its title appears on and all three counted meetings.
#
# A criterion every tier fails in the same way discriminates nothing. It
# subtracted a flat two points of ten from every score, compressing the
# band without measuring anything -- the mirror of one every tier passes.
#
# They are not deleted, because they remain the only signal separating a
# reader who opened the window from one who sampled it. Reported, not
# scored.
DERIVED_FROM_ROWS = ("distinct_owners", "meetings_read", "turns_read")

# Nothing here is restated by the brief. The window's dates are prose, but
# the report does not ask for them back -- an earlier task in this tree was
# handing away 10% of its reward that way.
RESTATED_FROM_BRIEF: tuple[str, ...] = ()
