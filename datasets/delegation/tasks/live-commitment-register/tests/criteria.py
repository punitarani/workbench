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
DELIVERABLE = "live_commitments.json"

# The list in the deliverable that carries one entry per live commitment.
ROWS = "live"

# Who owes it, in which standing meeting, and by when.
# Both ends of the chain and its length. A reader who finds the last
# statement and stops has `due` and neither of the others; one who finds
# the first has `first_due` and neither of the others. None is derivable
# from the other two and no system in this world records any of them.
# Who owes it, in which standing meeting, by when, and from what date.
#
# FOUR here and FIVE on the world this task was ported from, and the
# divergence is measured rather than inherited. `superseded` moved to a
# field on 2026-08-29, re-scored on saved deliverables with no sweep
# re-run:
#
#                                       opus     glm    kimi
#     (owner, meeting, due)             0.956   0.431   0.599
#     + first_due                       0.799   0.224   0.353
#     + superseded                      0.590   0.207   0.228
#     + first_due, superseded           0.590   0.190   0.217
#
# Three components leaves the strongest tier at 0.956, which is not a
# measurement of it. Five leaves the weakest at 0.190, which is barely
# above the level at which a criterion counts as touched at all.
#
# The count also produced three of this task's six unanimously-declined
# rows, every one of them a near miss -- 8 against 9, 10 against 9, 13
# against 12. A component readers get within one of, on rows they
# otherwise reconstruct correctly, collapses the row and reads to the gate
# as a defect. As a FIELD it degrades that row by 1/N and the work of
# counting is still measured.
#
# This world is denser than the one this came from: chains here run to 23
# supersessions where the sibling's run to 8. Its own
# `commitment-revision-register` reached the same conclusion independently,
# which is the check on this one.
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
FIELDS: dict[str, float] = {
    "meeting_id": 0.0,
    "said_at": 0.0,
    # Out of the key on 2026-08-29; see the note above KEY. Here it
    # degrades a row by 1/N instead of collapsing it, so the work of
    # counting supersessions is still measured.
    "superseded": 0.0,
}

# A count that is a tally of the rows this grading already checks. Paying
# for it again does not add signal, it multiplies the signal already there
# -- and it raises the floor, because an answer whose rows are wrong can
# still tally its own wrong rows correctly. It moves to the process
# dimension, where a reader who cannot add up their own register is still
# visible.
# `superseded_count` joins `distinct_owners` here because it is now
# exactly the sum of the rows' `superseded`: grading it in the reward
# would pay twice for one piece of work. In the diagnostic dimension a
# reader who cannot add up their own register is still visible, which is
# all that figure was ever worth -- and graded exact-match on a
# three-digit total it could only ever return zero.
# `meetings_read` joins them, and the reason is that it is not measuring
# anybody. Across the three tiers' saved trials it scores 1.00, 1.00 and
# 0.67 -- at ceiling for two of three, which is the definition of a
# criterion that has stopped separating readers. Counting the meetings in a
# stated window is a date-filtered query.
#
# `turns_read` STAYS, and the difference is measured rather than assumed:
# it reads 1.00, 0.33, 0.67, which is a criterion doing work. Counting
# turns means having opened the transcripts.
#
# Re-scored on the saved deliverables, no sweep re-run:
#
#                        opus     glm    kimi
#     keep both          0.795   0.441   0.282
#     drop meetings_read 0.772   0.378   0.239
#     drop turns_read    0.772   0.453   0.239
#     drop both          0.743   0.384   0.186
#
# Dropping both puts the weakest tier under the band, which is worth
# stating plainly: some of this task's band placement was resting on
# points every tier collected for reading the window at all. One of the two
# was free and one was not, and only the free one comes out. The empty
# register falls from 0.200 -- the bottom of the target band, arriving
# before the task starts -- to 0.111.
DERIVED_FROM_ROWS = ("distinct_owners", "superseded_count", "meetings_read")

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
