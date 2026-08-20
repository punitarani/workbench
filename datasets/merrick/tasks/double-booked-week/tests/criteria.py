"""Grading for the double-booking register.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

`KEY` is the person and both event ids. A person can be double-booked
several times in a week and two people can clash on the same pair of
events, so neither the person nor the pair names a row on its own.

The brief fixes the order of the two ids -- earlier start first, and the
lexicographically smaller id when two events start together -- because
without that rule the same clash keys two ways and F1 counts one row as
two misses. The tie-break matters here: this world schedules on a fixed
grid, so simultaneous starts are common rather than hypothetical.

`overlap_minutes` carries no tolerance. It is integer minutes computed from
two integer timestamps; a tolerance would only hide an off-by-one in the
boundary rule, which is the whole difficulty of the task.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable carrying one entry per clash.
ROWS = "double_bookings"
KEY = ("person", "first_event", "second_event")
FIELDS: dict[str, float] = {
    "first_title": 0.0,
    "second_title": 0.0,
    "date": 0.0,
    "overlap_minutes": 0.0,
}
