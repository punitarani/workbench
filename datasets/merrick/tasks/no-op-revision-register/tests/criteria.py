"""Grading for the no-op revision register.

The shape lives in `criteria_base`; this names the task's own rows, its row
key, and the tolerance on each field.

`KEY` is the document plus the version number. A document is revised up to
nine times in this record, so keying on the document alone collapses a
document's whole history into one row -- and row F1 would not show it,
because both sides dedupe identically and it still reads 1.000.

**This register targets the minority class on purpose.** Roughly one
revision in five declares no substantive change. A rule admitting the
majority scores ~0.9 for a model that simply takes everything; inverted,
over-admission destroys precision and under-reading destroys recall, so
both halves of F1 bite.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from criteria_base import *  # noqa: F401,F403

# The list in the deliverable carrying one entry per no-op revision.
ROWS = "no_op_revisions"
# The served version id names a version uniquely on its own -- `LEGAL!12.3`
# is version 3 of document 12 -- so no separate version column is graded.
# Grading one would be a free point: it is derivable from the key.
KEY = ("document_ref",)
# Author, date and document name are strings the record states outright.
# Exact is the only defensible tolerance for any of them.
FIELDS: dict[str, float] = {
    "author": 0.0,
    "revised_date": 0.0,
    "document_name": 0.0,
}
