"""Grading for the prebill narrative screen. The shape lives in
`criteria_base`; this names the task's own rows, its row key, and the
tolerance on each field.

`KEY` must distinguish every real row. A row here is a matter *and* a
timekeeper: keyed on either alone, one partner's week across eleven
matters collapses to a single row, and row F1 will not show it — both
sides dedupe identically and it still reads 1.000. It shows only in the
per-row check, as a ceiling no agent can reach.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The file the agent writes. Named here because the grading invocation
# reads it from this module -- it is the one thing about a task's
# grading that its criteria cannot derive from the oracle.
DELIVERABLE = "prebill_screen.json"

# The list in the deliverable that carries one entry per screened pair.
ROWS = "screened"
# The fields that together name exactly one row.
KEY = ("matter", "timekeeper")
# Per-field tolerance. `entries` is a count and is exact.
#
# `hours` and `fees_dollars` both carry 0.011, and the third decimal is
# doing real work in each direction:
#
# *Not 0.01.* `criteria_base._close` compares two floats with `abs(a - b)
# <= tol`, and the difference of two figures already cut to two decimals
# overshoots: `abs(0.12 - 0.13)` is 0.010000000000000009 and
# `abs(54.62 - 54.63)` is 0.010000000000005116, both greater than 0.01.
# A flat cent therefore rejects the one difference this tolerance exists
# to forgive — the direction an exact half rounds in, which is the most a
# correctly computed figure can differ by.
#
# *Not 0.02.* Two cents forgives more than a rounding direction. Summing
# the served `quantity_in_hours` and `total` — which arrive already cut
# to two decimals — drifts by up to 0.005 per entry, so at two cents
# every row of four or fewer flagged entries passes while doing exactly
# the round-then-sum the instruction spends a paragraph forbidding. At
# 0.011 a row is forgiven a rounding direction and nothing above it.
#
# `checks/verify.py` reads this dict and counts a round-then-sum
# disagreement only when it exceeds the tolerance here, so the design
# gate certifies rows the grader can actually see.
FIELDS: dict[str, float] = {
    "entries": 0.0,
    "hours": 0.011,
    "fees_dollars": 0.011,
}
