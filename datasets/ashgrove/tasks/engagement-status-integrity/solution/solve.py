"""Reference solver: engagements whose status the record contradicts.

Three checks, three different joins, one row per engagement that fails any
of them. Every rule is stated in terms the clio surface serves: the
status it shows now, the history of how it got there, the close date on
the matter, and the time logged against it.

The record's end is taken from the data rather than from a wall clock, so
the answer does not depend on when the report happens to be run.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("status_integrity.json")

DORMANT_DAYS = 3
DAY = 86_400


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    matters = {
        row[0]: {"engagement": row[1], "status": row[2]}
        for row in clio.execute("SELECT ticket_id, display_number, status FROM matters")
    }

    seconds: dict[str, int] = defaultdict(int)
    last_activity: dict[str, int] = {}
    latest = 0
    for ticket, quantity, when in clio.execute(
        "SELECT ticket_id, quantity_seconds, time FROM activities"
    ):
        seconds[ticket] += quantity
        last_activity[ticket] = max(last_activity.get(ticket, 0), when)
        latest = max(latest, when)

    # The status history: how many times it changed, and when it closed.
    changes: dict[str, int] = defaultdict(int)
    closed_at: dict[str, int] = {}
    for ticket, new_value, when in clio.execute(
        "SELECT ticket_id, new_value, time FROM matter_history "
        "WHERE field = 'status' ORDER BY time"
    ):
        changes[ticket] += 1
        if (new_value or "").strip().casefold() == "closed":
            closed_at[ticket] = when
        else:
            closed_at.pop(ticket, None)

    cutoff = latest - DORMANT_DAYS * DAY
    flagged = []
    for ticket, matter in matters.items():
        status = (matter["status"] or "").strip().casefold()
        dormant = status != "closed" and last_activity.get(ticket, 0) <= cutoff
        closed_time = closed_at.get(ticket)
        worked_after_close = (
            status == "closed"
            and closed_time is not None
            and last_activity.get(ticket, 0) > closed_time
        )
        churned = changes.get(ticket, 0) > 1
        if not (dormant or worked_after_close or churned):
            continue
        flagged.append(
            {
                "engagement": matter["engagement"],
                "status": matter["status"],
                "hours_logged": round(seconds.get(ticket, 0) / 3600, 2),
                "dormant": dormant,
                "worked_after_close": worked_after_close,
                "status_changes": changes.get(ticket, 0),
            }
        )
    flagged.sort(key=lambda row: row["engagement"])

    OUT.write_text(
        json.dumps(
            {
                "engagements_reviewed": len(matters),
                "dormant_count": sum(1 for row in flagged if row["dormant"]),
                "worked_after_close_count": sum(
                    1 for row in flagged if row["worked_after_close"]
                ),
                "churned_count": sum(1 for row in flagged if row["status_changes"] > 1),
                "flagged": flagged,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
