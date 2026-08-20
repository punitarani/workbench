"""Grading for <task>. The shape lives in `criteria_base`; this names the
task's own rows, its row key, and the tolerance on each field.

`KEY` must distinguish every real row. A collapsing key caps the ceiling
below 1.0 for reasons no agent can fix, and row F1 will not show it —
both sides dedupe identically and it still reads 1.000.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable that carries one entry per finding.
ROWS = "rows"
# The fields that together name exactly one row.
KEY = ("ref",)
# Per-field tolerance. 0.0 is exact; a money or hours field needs the
# smallest value that is not a real disagreement — a tolerance chosen for
# comfort is decoration, and one epsilon set "for safety" was larger than
# the rounding drift it existed to catch.
FIELDS: dict[str, float] = {}
