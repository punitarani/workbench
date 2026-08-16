"""Reference solver: engagements that moved backwards.

The status history is the whole of the evidence, and it has to be read in
order: a backward move is only visible as a pair of adjacent states, and
the hours that follow one are only countable once you know when it
happened.

Two traps. `waiting-client` is a hold with no place in the progression,
so changes into and out of it are changes without being backward moves.
And the record does not capitalise statuses consistently — the seed says
`Open`, the personas write `open` — so every comparison folds case.

Time is counted in whole days on purpose. Clio dates a time entry and a
field change; it never stamps an hour on either, here or in the real
product. An earlier draft of this task asked for the hours logged after
the *moment* of a backward move, which the oracle could compute from the
world's seconds and no agent could ever recover from the tools.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("status_integrity.json")

# The progression. A hold like waiting-client has no rank and so can never
# be a step backwards from anything.
RANK = {"open": 1, "in-progress": 2, "review": 3, "closed": 4}


def _rank(status: str | None) -> int | None:
    return RANK.get((status or "").strip().casefold())


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    matters = {
        row[0]: {"engagement": row[1], "status": row[2]}
        for row in clio.execute("SELECT ticket_id, display_number, status FROM matters")
    }

    activity: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for ticket, quantity, when in clio.execute(
        "SELECT ticket_id, quantity_seconds, time FROM activities"
    ):
        activity[ticket].append((when, quantity))

    changes: dict[str, int] = defaultdict(int)
    backward: dict[str, int] = defaultdict(int)
    reopened: set[str] = set()
    first_backward: dict[str, int] = {}
    for ticket, old_value, new_value, when in clio.execute(
        "SELECT ticket_id, old_value, new_value, time FROM matter_history "
        "WHERE field = 'status' ORDER BY time, rowid"
    ):
        changes[ticket] += 1
        if (old_value or "").strip().casefold() == "closed":
            reopened.add(ticket)
        before, after = _rank(old_value), _rank(new_value)
        if before is not None and after is not None and after < before:
            backward[ticket] += 1
            first_backward.setdefault(ticket, when)

    flagged = []
    for ticket, matter in sorted(matters.items(), key=lambda kv: kv[1]["engagement"]):
        if not backward.get(ticket):
            continue
        # Whole days, because that is the resolution the tools serve.
        since_day = first_backward[ticket] // 86_400
        seconds = sum(
            quantity
            for when, quantity in activity.get(ticket, ())
            if when // 86_400 >= since_day
        )
        flagged.append(
            {
                "engagement": matter["engagement"],
                "status": matter["status"],
                "status_changes": changes.get(ticket, 0),
                "backward_moves": backward[ticket],
                "reopened": ticket in reopened,
                "hours_from_backward_day": round(seconds / 3600, 2),
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "engagements_reviewed": len(matters),
                "reopened_count": len(reopened & set(matters)),
                "backward_move_count": sum(backward.values()),
                "never_moved_count": sum(
                    1 for ticket in matters if not changes.get(ticket)
                ),
                "flagged": flagged,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
