"""Grading for the live commitment register: three counts and the rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

**`KEY` carries the resolved date, and that is the whole design.** A
commitment is identified by who owes it, in which standing meeting, and by
when. "Cecile said Thursday" and "Cecile said Friday" are two different
commitments, one of which is dead, so reporting the superseded one is a
false positive rather than a wrong field — semantically right, and what
makes the arithmetic work. Measured on a 45-day window of the partial v6
bundle against a register built by a reader who takes each person's first
statement and stops:

    keyed (owner, meeting), date a field   row_f1 1.000  (28 of 28 rows)
    keyed (owner, meeting, due)            row_f1 0.179  ( 5 of 28 rows)

`row_facts` collapses rather than degrading because a wrong key means the
row is not matched at all — every field on it misses, and the invented row
draws `row_fields`' extra-row penalty on top.

**Why the date and not the word.** An earlier draft graded the deadline as
the token said out loud. That hands away the field: `eod` is 47-69% of live
answers depending on the window, so a reader who never opens a transcript
scores most of the column. The resolved date cannot be guessed — the
commonest single date holds 14% — and it is only computable from the
meeting the last statement was made in, which is what makes `meeting_id`
load-bearing rather than decorative.

**A key that can collapse two real rows would cap the ceiling invisibly.**
Both sides dedupe identically, so row F1 still reads 1.000 and the loss
shows only in the per-row check. Measured: of 176 (meeting, speaker) pairs
that carry a commitment at all, 2 carry more than one and 1 names two
different deadlines. So "one live commitment per person per standing
meeting" is a true statement about this corpus rather than a grading
convenience, and `checks/verify.py` asserts the row count before and after
keying.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's grading
# that its criteria cannot derive from the oracle.
DELIVERABLE = "slippage_register.json"

# The list in the deliverable that carries one entry per live commitment.
ROWS = "live"

# Who owes it, in which standing meeting, and by when.
# Who owes it, in which standing meeting, by when, and how many times
# they moved that date LATER.
#
# `slips` is what separates this register from its two siblings. Both of
# those need the chain's ENDS -- the last statement for `due`, the first
# for `first_due`, the count of rooms for `superseded`. None of them needs
# the dates in between. This one does: a slip is a comparison of two
# consecutive resolved dates, so every link has to be read AND resolved
# against its own meeting. A reader who finds the endpoints and stops has
# nothing here.
#
# `slips` came OUT of the key on 2026-08-29 and grades as a field instead.
# Measured on saved deliverables, no sweep re-run:
#
#                                       opus     glm    kimi
#     (owner, meeting)                  0.974   0.573   0.691
#     + due                             0.923   0.451   0.369
#     + first_due                       0.632   0.276   0.226
#     + due, slips                      0.598   0.242   0.151
#     + first_due, slips                0.529   0.215   0.134
#
# 0.134 is beneath the level at which a criterion counts as having been
# touched at all, so at five components the weakest tier was not being
# measured, it was being excluded. Four leaves it 0.226 and something to
# score.
#
# The paragraph above still holds and is the reason `slips` is graded at
# all rather than dropped: it is the one component that needs every link
# in the chain rather than its ends. As a FIELD it degrades a row by 1/N
# instead of deciding whether the row exists, so the work of reading every
# link is still paid for -- it just no longer costs the whole row.
#
# The sibling `assignment-slippage-register` was retired for exactly this
# shape, at 0.137 for its strongest tier. The difference here is that the
# commitment rule is easier than the assignment rule, which leaves room
# for a chain on top of it.
KEY = ("owner", "meeting", "due", "first_due")

# What is left once the key has taken three of the five fields. Both are
# strings the record states outright -- a meeting id and its start -- so
# exact is the only defensible tolerance; anything else would be
# decoration.
#
# They are graded rather than dropped because they are the *evidence*: a
# register that names the right date and cannot say which room it was said
# in has not been read, it has been reconstructed, and with the date
# already in the key the two would otherwise be indistinguishable.
FIELDS: dict[str, float] = {"meeting_id": 0.0, "said_at": 0.0, "slips": 0.0}

# A count that is a tally of the rows this grading already checks. Paying
# for it again does not add signal, it multiplies the signal already there
# -- and it raises the floor, because an answer whose rows are wrong can
# still tally its own wrong rows correctly. It moves to the process
# dimension, where a reader who cannot add up their own register is still
# visible.
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
#                      never saw a supersession, so they report zero
#                      against a true 62. It is not derivable from `live`,
#                      because the rows are precisely what supersession
#                      removed.
