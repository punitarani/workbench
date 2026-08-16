"""Reference solver: who worked on what, and what it was worth.

One row per person and engagement they logged time to. The arithmetic is
plain — hours, the billable share of them, and the fees those billable
hours carry at each entry's own rate — and the work is in the reading:
the firm's time sits in thirteen hundred entries, fifty to a page, and a
page skipped is a row wrong or a row missing.

Rates live on the entry rather than on the person, because a rate is
what was charged at the time and staff move between grades. Summing
hours and multiplying once by anyone's current rate gives a different,
wrong number.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("time_allocation.json")


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)

    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    engagements = dict(
        clio.execute("SELECT ticket_id, display_number FROM matters")
    )

    totals: dict[tuple[str, str], dict] = defaultdict(
        lambda: {"seconds": 0, "billable_seconds": 0, "entries": 0, "cents": 0}
    )
    for ticket, person, seconds, rate_cents, billable in clio.execute(
        "SELECT ticket_id, person, quantity_seconds, rate_cents, billable "
        "FROM activities"
    ):
        row = totals[(person, ticket)]
        row["entries"] += 1
        row["seconds"] += seconds
        if billable:
            row["billable_seconds"] += seconds
            # A rate is not guaranteed. 234 entries carry none, and one of
            # them is marked billable: billable hours it is, fees it is
            # not, because there is no rate to charge them at.
            row["cents"] += seconds * (rate_cents or 0) / 3600

    rows = []
    for (person, ticket), row in sorted(
        totals.items(),
        key=lambda item: (
            names.get(item[0][0], item[0][0]),
            engagements.get(item[0][1], item[0][1]),
        ),
    ):
        rows.append(
            {
                "person": names.get(person, person),
                "engagement": engagements.get(ticket, ticket),
                "entries": row["entries"],
                "hours": round(row["seconds"] / 3600, 2),
                "billable_hours": round(row["billable_seconds"] / 3600, 2),
                "fees_dollars": round(row["cents"] / 100, 2),
            }
        )

    busiest = max(
        rows, key=lambda row: (row["hours"], row["person"], row["engagement"])
    )
    OUT.write_text(
        json.dumps(
            {
                "entries_total": sum(row["entries"] for row in rows),
                "pairs": len(rows),
                "total_hours": round(sum(row["hours"] for row in rows), 2),
                "total_billable_hours": round(
                    sum(row["billable_hours"] for row in rows), 2
                ),
                "total_fees_dollars": round(
                    sum(row["fees_dollars"] for row in rows), 2
                ),
                "busiest_person": busiest["person"],
                "busiest_engagement": busiest["engagement"],
                "allocations": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
