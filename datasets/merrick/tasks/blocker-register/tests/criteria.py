"""Grading for the blocker register: two counts and the rows.

**Nothing in this key is in any sentence.** Every other register in this
tree grades a date the speaker said out loud; here the speaker says only
that they are stuck, and all three graded facts come from the meetings the
complaint was made in.

That is the joint dependency, and it is a stronger form than the
commitment registers manage. There, a reader who finds the last statement
has `due` for free -- it is written in the turn. Here, `first_raised`,
`last_raised` and `raised_count` are the two ends of a chain and its
length, and NONE of them can be read off a turn. A reader who finds every
complaint but places them in the wrong order gets all three wrong while
having extracted perfectly.

At a per-extraction accuracy `a`, a row needing `k` independent facts is
right with `a**k`; the point of this family is that `k` is not reachable
by reading harder, only by reading everything.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

DELIVERABLE = "blocker_register.json"

ROWS = "blockers"

# Who is stuck, in which standing meeting, and the two ends of the chain.
#
# `raised_count` moves to a field. Chosen by re-scoring the same saved
# deliverables under every candidate -- no sweep re-run:
#
#     (owner, meeting)                              0.953 / 0.932
#     (owner, meeting, first_raised)                0.785 / 0.604
#     (owner, meeting, first_raised, last_raised)   0.729 / 0.356   <- chosen
#     (owner, meeting, raised_count)                0.561 / 0.137
#     (owner, meeting, first, last, raised_count)   0.561 / 0.137
#
# `raised_count` is what collapses the weakest tier: adding it takes 0.729
# to 0.561 for the strongest and 0.356 to 0.137 for the weakest, which puts
# the criterion below the level at which a tier is being measured at all.
# It is the hardest of the three because it needs every meeting in between,
# where the two ends need only the outermost -- so it grades as a field,
# where getting it wrong costs part of a row rather than the whole row.
# Who is stuck, in which standing meeting, both ends of the chain, and how
# many meetings it was raised in.
#
# FIVE here and FOUR on the sibling world, and the difference is the
# corpora rather than an inconsistency. Measured, on the same rule and the
# same brief:
#
#                                              merrick        delegation
#     (owner, meeting)                          1.000            0.953
#     (owner, meeting, first_raised)            0.900            0.785
#     (owner, meeting, first, last)             0.900            0.729
#     (owner, meeting, first, last, count)      0.700            0.561
#
# This world's blockers are shallower: 9 of 20 rows have first == last, so
# the two ends cost almost nothing and the strongest tier reads 0.900 --
# 0.838 as a headline, above the band. The count is the only component that
# separates anyone here.
#
# On the denser world the same component collapsed the weakest tier to
# 0.137 and put it below the band, so it grades as a field there. A key is
# chosen against a corpus, and two worlds carrying one family do not have
# to agree on one.
KEY = ("owner", "meeting", "first_raised", "last_raised", "raised_count")

# The rooms the chain begins and ends in.
#
# This was EMPTY, and the floors caught it: `row_fields` over no fields has
# nothing to disagree with and returns 1.0, so an empty register scored
# 0.500 and an answer with no work in it at all scored 0.300 -- three of
# ten points for a criterion that could not fail. A measurement whose
# outcome is fixed by construction is not a measurement.
#
# These two earn their place beyond fixing that. They are the EVIDENCE: a
# register that names the right dates and cannot say which rooms they were
# said in has been reconstructed rather than read, and with both dates
# already in the key the two would otherwise be indistinguishable.
FIELDS: dict[str, float] = {
    "first_meeting_id": 0.0,
    "last_meeting_id": 0.0,
}

# The census fields move here, and stop paying.
#
# A reviewer with legal-ops knowledge called them what they are: audit
# fields no partner wants, in a deliverable that should read as a table.
# They cannot simply be deleted -- they are the one signal separating a
# reader who opened the whole window from one who sampled it -- so they
# inform without moving the number, which is what this dimension is for.
#
# It also removes two of ten points that every tier earns for free. An
# answer that reads the window and extracts nothing scored 0.200 on those
# alone, which is the bottom of the target band arriving before the task
# starts.
DERIVED_FROM_ROWS = ("distinct_owners", "meetings_read", "turns_read")


RESTATED_FROM_BRIEF: tuple[str, ...] = ()
