"""Grading for the commitment revision register: two counts and the rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

**`KEY` carries the revision count, and that is what this task adds.** The
parent task, `standing-commitment-register`, keys on (owner, meeting, due)
and asks for the number of discarded commitments as a single scalar,
`superseded_count`. That scalar was measured across six trials of two
tiers and **not one of them earned it**:

    oracle 132   opus 123, 124, 118   glm 98, 134, 95

Those answers straddle the truth rather than clustering away from it, so
the key is right and the readers are merely imprecise -- opus within 6-11%,
scored 0.000 three times out of three. An exact-match grade on a
three-digit number derived from thousands of judgement calls can only ever
return zero, and a cliff to zero says nothing about what the agent knew.
This file's own base module has said that about invented rows since it was
written; the scalar was the same mistake one level up.

So the count moves onto the rows, one per (owner, meeting) pair, where it
earns partial credit and a reader can see *which* chains were misread.

**Why the key and not a field.** This dataset has already measured the
difference, on the `due` date, and it is not a matter of degree:

    keyed (owner, meeting), date a field   row_f1 1.000  (28 of 28 rows)
    keyed (owner, meeting, due)            row_f1 0.179  ( 5 of 28 rows)

A hard fact in a field moves `row_facts` by one part in N. The same fact
in the key makes the row a non-match: it misses, every field on it misses,
and the invented row draws the extra-row penalty. The reason to accept
that here is semantic rather than arithmetic -- "Samir owes this by 13 May,
having moved it twice" is a materially different claim from "…having moved
it eleven times", and reporting the second when the first is true is a
wrong row, not a right row with a wrong figure.

**What makes it hard is joint dependency, and that is the whole point.**
Every other row key in this family hinges on ONE extraction: the person's
last qualifying statement. Adding more such rows cannot lower a strong
reader's score, because F1 is per-row -- a register of 117 rows scores the
same as one of 26 when each row still turns on a single sentence. Measured
on this corpus: a month-end snapshot design would have produced 117 rows
and left opus's F1 within a point of where it already sits.

The revision count is the first figure here that depends on the *whole*
chain. A reader who finds the last statement and stops is right about the
date and wrong about the count. At a per-statement accuracy of `a`, a row
requiring `k` statements is right with probability `a^k`; the chains on
this window run 1 to 23 statements long, median 6.

**The column is not degenerate**, which had to be checked rather than
assumed -- a constant column is a criterion an agent scores full marks on
without looking. Twelve distinct values over 26 rows; the modal value, 0,
covers 19% of them, so a reader who writes "never revised" on every row
scores under a fifth of the column and loses every other row outright.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's grading
# that its criteria cannot derive from the oracle.
DELIVERABLE = "commitment_revisions.json"

# The list in the deliverable that carries one entry per live commitment.
ROWS = "live"

# Who owes it, in which standing meeting, by when, from what date it
# started, and over how many earlier statements.
#
# Both ends of the chain and its length. A reader who finds the last
# statement and stops has the `due` and nothing else; one who finds the
# first and stops has `first_due` and nothing else. Only a reader who built
# the whole chain has all three, which is the joint dependency this task
# exists to measure -- at a per-statement accuracy of `a`, a row needing
# `k` statements is right with probability `a**k`.
# Who owes it, in which standing meeting, by when, and from what date.
#
# `superseded` moves to a field. Chosen by re-scoring the same saved
# deliverables under every candidate -- no sweep re-run:
#
#     (owner, meeting)                        0.977 / 0.977 / 0.894
#     (owner, meeting, due)                   0.921 / 0.886 / 0.650
#     (owner, meeting, due, first_due)        0.704 / 0.671 / 0.370
#     (owner, meeting, due, superseded)       0.568 / 0.500 / 0.271
#     (owner, meeting, due, first_due, sup)   0.511 / 0.466 / 0.261
#
# At five components the weakest tier sat at 0.261 and its headline fell
# below the band once the census counts stopped paying for reading the
# window. Four keeps both ends of the chain in the key -- which is what
# this register is for -- while leaving the tier something to score.
#
# This world is denser than its sibling: 200 commitments in 383 meetings
# against 154 in 512, so the same key is harder here and the two datasets
# do not have to agree on one.
KEY = ("owner", "meeting", "due", "first_due")

# What is left once the key has taken four of the six fields. Both are
# strings the record states outright -- a meeting id and its start -- so
# exact is the only defensible tolerance.
#
# They are graded rather than dropped because they are the *evidence*: a
# register that names the right date and cannot say which room it was said
# in has not been read, it has been reconstructed.
FIELDS: dict[str, float] = {
    "superseded": 0.0,
    "meeting_id": 0.0,
    "said_at": 0.0,
}

# Tallies of the rows this grading already checks. Paying for them again
# does not add signal, it multiplies the signal already there -- and it
# raises the floor, because an answer whose rows are wrong can still tally
# its own wrong rows correctly.
#
# `superseded_count` joins `distinct_owners` here for a reason specific to
# this task: it is now exactly the sum of the rows' `superseded`, so
# grading it in the reward would pay twice for one piece of work. In the
# diagnostic dimension a reader who cannot add up their own register is
# still visible, which is all that figure was ever worth.
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
#   meetings_read   how much of the window was opened. Nothing else
#                   captures it, and it is the one number a reader who
#                   sampled cannot fake from the rows they found.
#   turns_read      the same, one level down. A reader who opened every
#                   meeting and skimmed each is visible here and nowhere
#                   else.
