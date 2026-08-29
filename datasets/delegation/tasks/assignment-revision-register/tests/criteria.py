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

DELIVERABLE = "assignment_register.json"

ROWS = "assignments"

# Who was told, in which standing meeting, and by when.
#
# `first_due` and `superseded` were IN the key and are now fields, which is
# the difficulty law run backwards. A hard fact in the key collapses row F1;
# in a field it degrades the score by one part in N. That is normally used
# to make a task harder -- it took one register from 1.000 to 0.179 -- and
# here it was needed the other way.
#
# Measured on the same saved deliverables, re-scored under each candidate
# key rather than by re-running anything:
#
#     (owner, meeting)                       0.695 / 0.614 / 0.608
#     (owner, meeting, due)                  0.338 / 0.159 / 0.154
#     (owner, meeting, due, superseded)      0.207 / 0.067 / 0.039
#     (owner, meeting, due, first_due, sup)  0.178 / 0.052 / 0.032
#
# At five components every tier sat inside the band on its headline while
# extracting almost nothing -- 32 of 39 rows declined by every trial of
# every tier -- which is the ceiling defect from the other end. The
# assignment rule is simply harder than the promise rule: the owner of a row
# is never the speaker, so the whole chain has to be attributed before any
# of it can be dated.
# Who was told, and in which standing meeting.
#
# ATTRIBUTION is what this family is about: the owner of a row is never the
# person who said the words, and one turn may name three colleagues of whom
# one is an assignee, one a recipient and one a purpose clause. The dates
# and the chain length are graded as fields, where a wrong one costs part
# of a row instead of the whole row.
#
# Chosen by re-scoring the same saved deliverables under every candidate --
# no sweep re-run -- and then re-chosen after the census counts stopped
# paying:
#
#     (owner, meeting)                       0.695 / 0.614 / 0.608
#     (owner, meeting, due)                  0.338 / 0.159 / 0.154
#     (owner, meeting, due, first_due, sup)  0.178 / 0.052 / 0.032
#
# At three components the task was in band ONLY because two of its ten
# points came free from the census counts, which every tier earns for
# reading the window. With those moved to the diagnostic dimension the same
# key put two tiers below 0.11, and the propping-up became visible.
KEY = ("owner", "meeting")

# What is left once the key has taken five of the seven fields. Both are
# strings the record states outright -- a meeting id and its start -- so
# exact is the only defensible tolerance.
#
# They are graded rather than dropped because they are the *evidence*: a
# register that names the right dates and cannot say which room they were
# said in has been reconstructed rather than read.
# The chain facts, still graded, but no longer able to void a row that
# named the right person, room and date.
# Everything the chain says, graded per row rather than in the key.
FIELDS: dict[str, float] = {
    "due": 0.0,
    "first_due": 0.0,
    "superseded": 0.0,
    "meeting_id": 0.0,
    "said_at": 0.0,
}

# Tallies of the rows this grading already checks. Paying for them again
# multiplies the signal already there and raises the floor, because an
# answer whose rows are wrong can still count its own wrong rows correctly.
# They move to the process dimension, where a reader who cannot add up
# their own register is still visible.
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
