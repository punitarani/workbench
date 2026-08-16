"""Reference solver: WIP and utilization at the end of the record.

Every rule here is one an agent can apply through the tools. An engagement
is client work when it has a client — the way Clio models a matter — not
because its title happens to start with a particular word. Engagements are
named by their display number, which is what clio serves; the world's
internal `tkt-` ids never appear on the surface and must never be asked for.

Three traps that move many numbers at once: the firm's own engagements
carry no client and no WIP; people with no standard rate carry no value
however much they log; and non-billable time counts toward a person's day
but never toward WIP.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("wip_review.json")


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    names = dict(clio.execute("SELECT person_id, name FROM people"))
    matters = {
        row[0]: {"display_number": row[1], "client": row[2]}
        for row in clio.execute(
            "SELECT ticket_id, display_number, client_org FROM matters"
        )
    }
    internal = {t for t, m in matters.items() if m["client"] is None}

    per_engagement: dict[str, dict] = defaultdict(
        lambda: {"billable_seconds": 0, "value_cents": 0, "staff": set()}
    )
    per_person: dict[str, dict] = defaultdict(
        lambda: {"logged_seconds": 0, "billable_seconds": 0, "value_cents": 0}
    )
    for ticket, person, seconds, rate, billable in clio.execute(
        "SELECT ticket_id, person, quantity_seconds, rate_cents, billable "
        "FROM activities"
    ):
        value = seconds * (rate or 0) // 3600 if billable else 0
        person_row = per_person[person]
        person_row["logged_seconds"] += seconds
        if billable:
            person_row["billable_seconds"] += seconds
            person_row["value_cents"] += value
        if ticket in internal:
            continue
        row = per_engagement[ticket]
        row["staff"].add(person)
        if billable:
            row["billable_seconds"] += seconds
            row["value_cents"] += value

    # Every client engagement appears, including any with no time against it
    # yet: a quiet engagement is still on the book, and leaving it out would
    # make the count depend on whether anyone happened to log to it.
    empty = {"billable_seconds": 0, "value_cents": 0, "staff": ()}
    engagements = [
        {
            "engagement": matters[ticket]["display_number"],
            "billable_hours": round(row["billable_seconds"] / 3600, 2),
            "wip_dollars": round(row["value_cents"] / 100, 2),
            "staff_count": len(row["staff"]),
        }
        for ticket, row in sorted(
            ((t, per_engagement.get(t, empty)) for t in matters if t not in internal),
            key=lambda kv: matters[kv[0]]["display_number"],
        )
    ]
    people = [
        {
            "name": names.get(person, person),
            "logged_hours": round(row["logged_seconds"] / 3600, 2),
            "billable_hours": round(row["billable_seconds"] / 3600, 2),
            "utilization_pct": round(
                100 * row["billable_seconds"] / row["logged_seconds"], 1
            )
            if row["logged_seconds"]
            else 0.0,
        }
        for person, row in sorted(
            per_person.items(), key=lambda kv: names.get(kv[0], kv[0])
        )
    ]
    total_value = sum(row["value_cents"] for row in per_engagement.values())
    total_billable = sum(row["billable_seconds"] for row in per_engagement.values())
    OUT.write_text(
        json.dumps(
            {
                "client_engagements": len(matters) - len(internal),
                "internal_engagements": len(internal),
                "total_client_wip_dollars": round(total_value / 100, 2),
                "blended_rate_dollars_per_hour": round(
                    total_value / 100 / (total_billable / 3600), 2
                )
                if total_billable
                else 0.0,
                "engagements": engagements,
                "people": people,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
