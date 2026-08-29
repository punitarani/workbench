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
FIELDS: dict[str, float] = {"first_meeting_id": 0.0, "last_meeting_id": 0.0}

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
