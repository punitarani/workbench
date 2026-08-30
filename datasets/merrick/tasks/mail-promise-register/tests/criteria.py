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

# **It now does read above the band, and the window lever is blocked.**
# Measured 2026-08-30 with three answered opus trials -- 0.889, 0.714 and
# 1.000, a mean of 0.868, with `owed.f1` at 0.952.
#
# Widening is what would fix the score, and it costs completion this task
# cannot pay:
#
#     window   words   promises/person
#        61d  95,915              1.7   <- shipped; opus 0.868
#        90d 136,107              2.1
#       120d 167,392              2.3
#   delegation
#        61d 118,888              3.0   <- opus 0.456, glm 0.19, kimi 0.14
#
# The interpolation says 90 to 120 days would put every tier in band. The
# completion measurement says it cannot be run: opus already answers this
# register 2 times in 11 at 95,915 words, and delegation's at 118,888
# words is where glm abandons outright. A 90-day window here is MORE text
# than the register two tiers already fail to finish.
#
# So the difficulty lever and the completion lever pull opposite ways on
# the mail surface, and the key offers nothing between them -- adding
# `message_ref`, `said_on` or `subject` moves the strongest tier
# 0.929 -> 0.929, because the evidence fields are right whenever the row
# is.
#
# Held pending opus at k=9. Three answered trials spanning 0.714 to 1.000
# is a wide spread, and 0.868 on n=3 is not a verdict.

# **If this task ever reads above the band, the lever is the WINDOW, not
# the key.** Measured 2026-08-30, before it was needed:
#
#     window   messages   promises   rows
#        61d        530         24     14   <- as shipped
#        90d        762         32     15
#       120d        953         39     17
#       182d       1399         57     18
#
# Widening barely adds rows -- 14 to 18 across the whole recording -- and
# nearly doubles the promises PER PERSON, 1.7 to 3.2. That is the thing
# that makes this hard: the register asks for the live promise, so what
# costs a reader is how many superseded ones stand in front of it. The
# sibling register measured the same lever on transcripts and found the
# strongest tier at 1.000 on a 42-day window and 0.795 on a 147-day one.
#
# The key offers nothing. Adding `message_ref`, `said_on` or `subject` to
# it moves the strongest tier 0.929 -> 0.929: the evidence fields are
# right whenever the row is.

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
