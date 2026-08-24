"""Reference solver: the revisions whose comment says nothing changed.

STAGED. `WINDOW_DAYS` is not chosen; `main()` refuses while it is None.
Fill it from a measurement of the finished record, never from intuition.

**The rule is inverted on purpose, and the measurement is why.** The first
draft admitted revisions whose comment named an edit -- added, removed,
revised, updated. Measured on the record that admits **98 of 119**, so a
model that reports every revision it can see scores about 0.9 on row F1
without reading a word. Difficulty cannot come from a rule that is almost
always true.

Inverted, the target is the minority: 22 of 119, about one revision in
five. Over-admitting now destroys precision and skimming destroys recall,
so both halves of F1 bite. That is the same shape as every register in this
dataset that landed in band.

**What makes it hard is the shape of the prose, not the rule.** These
comments run to a median of 69 words. They open by describing what the
document *is*, list what was checked, and admit in one clause that nothing
was altered. The clause is the row; the seventy words around it are
scenery, and they read exactly like evidence of work.

**A field was cut here after measuring it.** The draft carried
`author_logged_time` -- whether the reviser recorded time that day. It is
true for **98 of 98** admitted rows: everybody who touches a document logs
time that day. A constant column grades nothing, and it would have looked
like a cross-surface check while being a free point.
"""

import datetime
import json
import os
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("no_op_revisions.json")

# Calendar days, not working days: the cutoff is `WINDOW_DAYS * 86_400`
# and counts every day, while the brief quotes the working-day figure
# because that is what a reader thinks in. The two differ by every weekend
# inside the window, and the verifier takes this same integer, so filling
# it from the working-day figure would shorten the corpus silently and the
# cross-check could not see it.
#
# 46 calendar days = 34 working days, ending Thursday 19 February 2026,
# which is the boundary the brief states. Measured on the shipped record by
# `measure_windows.py`, which drives this solver rather than a copy of it:
# ~235 version comments in front of the reader for 20 rows. The floor is
# twelve rows; a fortnight gives seven and does not clear it.
WINDOW_DAYS: int = 46

# The admitted phrases, closed, and PLURAL. The singulars this firm also
# writes -- `no substantive change` 13 times, `no edit made` 6, `no
# substantive edit` 4, `no change made` 2, `no edits were made` 1 -- are
# deliberately absent. That asymmetry is the rule and it is where the
# task's difficulty lives: 26 near-misses against 20 rows, every one of
# them a plain declaration that nothing changed.
#
# `no substantive revisions` was on this list and fired on nothing: 0 of
# 1,118 version comments. A form that grades no instances is a column of
# nothing dressed as a rule, so it is gone from here and from the brief.
NO_OP = re.compile(
    r"\bno substantive (?:edits|changes)\b"
    r"|\bno changes (?:were )?made\b"
    r"|\bno edits made\b",
    re.IGNORECASE,
)


def main() -> None:
    imanage = sqlite3.connect(f"file:{STATE / 'imanage.db'}?mode=ro", uri=True)

    # Seconds from the world's epoch, not a date string. Comparing a served
    # `time` against an ISO date compiles, runs, and windows on a
    # lexicographic accident.
    cutoff = WINDOW_DAYS * 86_400
    epoch = datetime.datetime.fromisoformat(
        dict(imanage.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(imanage.execute("SELECT person_id, name FROM people"))
    # The row key has to be an id the tools actually emit. `doc-000012` is
    # internal: no iManage surface returns it as a field, so an agent has no
    # way to write it and a perfect answer would score zero on every row.
    # `LEGAL!{number}.{version}` is what `get_document_versions` returns and
    # what every profile carries as `id`.
    served = dict(imanage.execute("SELECT document_id, document_number FROM documents"))
    names = dict(imanage.execute("SELECT document_id, name FROM documents"))

    rows = []
    versions_read = 0
    for document_id, version, author, comment, when in imanage.execute(
        "SELECT document_id, version, author, comment, time FROM versions "
        "ORDER BY document_id, version"
    ):
        if when >= cutoff:
            continue
        # Version 1 is the creation, not a revision. It is projected with a
        # fixed comment that carries no admitted phrase, so the rule already
        # excludes it -- but relying on that couples this register to the
        # wording of a projection constant it does not own.
        if version <= 1:
            continue
        versions_read += 1
        if not NO_OP.search(comment):
            continue
        rows.append(
            {
                "document_ref": f"LEGAL!{served[document_id]}.{version}",
                "author": people.get(author, author),
                "revised_date": (epoch + datetime.timedelta(seconds=when))
                .date()
                .isoformat(),
                "document_name": names.get(document_id, ""),
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "window_end": (epoch + datetime.timedelta(seconds=cutoff - 1))
                .date()
                .isoformat(),
                "versions_read": versions_read,
                "no_op_revisions": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
