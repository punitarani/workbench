"""Grading for the mail promise register: three counts and the rows.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

**`KEY` carries the resolved date, and that is the whole design.** A promise
is identified by who made it and by when it falls due. "Rosalie said
Tuesday" and "Rosalie said Friday" are two different promises, one of which
is dead, so reporting the superseded one is a false positive rather than a
wrong field. Keyed on the owner alone, the row set would be trivial -- every
person who ever promised is easy to enumerate -- and the date, which is the
only hard part, would degrade to a field tolerance instead of deciding the
row.

**Why the date and not the word.** `eod` is a third of the admitted forms
in this window, so a reader who never resolves anything scores most of a
word-valued column. The resolved date cannot be guessed: the commonest
single due date holds 14% of the register, and computing one at all
requires knowing the day the message was sent.

**One row per person, so the key cannot collide.** Measured on this window:
every sender who promises at all has exactly one live promise by
construction, because supersession keeps the last. The verifier asserts the
row count before and after keying.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes.
DELIVERABLE = "owed.json"

# The list carrying one entry per live promise.
ROWS = "owed"

# **The window lever does not reach this task's difficulty, measured
# 2026-08-30 once the weakest tier had three graded trials.**
#
# kimi reads 0.059, 0.139, 0.224 -- a mean of 0.141, below the band -- and
# that is now a measurement rather than a small sample. The reason is
# supersession depth, and shortening the window barely touches it:
#
#     window   words   promises  rows  superseded  per person
#        45d  92,676         32    12          20         2.7
#        61d 118,888         36    12          24         3.0
#     merrick  95,915        24    14          10         1.7
#
# Cutting to 45 days removes a quarter of the reading and moves
# promises-per-person from 3.0 to 2.7, where the sibling world sits at 1.7
# and its kimi scores 0.536. The volume is fixable and the density is not:
# this world's people re-promise, which is what the register asks a reader
# to see through.
#
# So the window is a completion lever, not a difficulty one, and the two
# were worth separating before spending a rebuild on it.
#
# (Retained below: the volume measurement, which is still the right lever
# if completion rather than score is the problem.)

# **If the tiers cannot finish this, the lever is the WINDOW.** Measured
# 2026-08-30, when opus answered 2 of 3 and glm 1 of 3 while the same
# family on the sibling world answers 3 of 3:
#
#     window   messages     words   promises   rows
#        45d        481    92,676         32     12
#        50d        509    97,236         34     12
#        55d        571   107,429         35     12
#        61d        636   118,888         36     12   <- as shipped
#
# The sibling's 61-day window holds 530 messages and 95,915 words, and is
# completed reliably by every tier. This one holds 24% more text for the
# SAME twelve rows -- the extra reading buys no extra register.
#
# So 50 days is the fallback: the same row count at the sibling's word
# budget. It is not free, and that is why it is a fallback rather than a
# fix. One row moves -- Yuki Tanabe's live promise is 2026-03-06 over 61
# days and 2026-02-10 over 50, because the later message that supersedes
# it falls outside the shorter window. A shorter window is a different
# measurement, not a cheaper one, so it is taken only if the current task
# proves unmeasurable rather than merely expensive.

# Who owes it, and by when.
KEY = ("owner", "due")

# What is left once the key has taken two of the five fields. All three are
# strings the record states outright, so exact is the only defensible
# tolerance. They are graded rather than dropped because they are the
# *evidence*: a register naming the right date that cannot say which message
# carried it has been reconstructed rather than read.
FIELDS: dict[str, float] = {"message_ref": 0.0, "said_on": 0.0, "subject": 0.0}

# Nothing here is a tally of the rows. One row per person means a count of
# owners WOULD be one, which is why the register does not ask for it: a
# scalar that restates the row count pays twice for the same work and lifts
# the floor, because a wrong row set can still be counted correctly.
# The census count moves out of the reward and stops paying, for the same
# reason it did on the blocker register: `messages_read` is a date-filtered
# query away, and a reader who opens the window and extracts NOTHING was
# collecting a tenth of the reward for it.
#
# Measured here rather than argued. The no-comprehension floor for dumping
# every candidate read 0.376 and the row set contributes 0.05 of that -- a
# dump of 530 messages against 14 true rows is precision 0.026. The rest
# was the two scalars, and one of them is a census.
#
# `superseded_count` STAYS in the reward and the difference is the work.
# It counts promises that were overtaken by a later one, which requires
# applying the rule and then ordering what it finds -- and those promises
# appear in NO row of the register, so it is independent signal rather
# than the row set tallied a second time. That distinction is the whole
# test for whether a scalar belongs here.
DERIVED_FROM_ROWS: tuple[str, ...] = ("messages_read",)

# `window_end` is the boundary the brief states outright. The deliverable
# carries it because it is a useful self-check for the reader -- an answer
# whose rows run past its own stated boundary is visibly wrong -- but it is
# not graded. Paying for a value the brief hands over is how an earlier task
# in this dataset gave away 10% of its reward.
RESTATED_FROM_BRIEF: tuple[str, ...] = ("window_end",)
