"""Reference solver: engagement status before the partners' status meeting.

Each engagement was opened by a client contact, and that contact's mail
is the evidence of where it stands. An engagement is only clear when the
firm owes that client nothing: if the client's last message in any
thread is still unanswered, the engagement is waiting on the firm no
matter how many hours have been poured into it.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("closeout.json")


def main() -> None:
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    names = dict(clio.execute("SELECT person_id, name FROM people"))
    matters = {
        t: (d, r, o)
        for t, d, r, o in clio.execute(
            "SELECT ticket_id, description, responsible_person, originating_person "
            "FROM matters"
        )
    }
    external_people = {
        p
        for (p,) in clio.execute(
            "SELECT person_id FROM people WHERE affiliation='external'"
        )
    }
    # Client work is work a client asked for. The title is not the test —
    # "Firm — 2026 peer review preparation" was opened by the outside peer
    # reviewer and is a client engagement; an engagement a partner opened on
    # the firm's own behalf is not, whatever it is called.
    internal = {t for t, (_d, _r, o) in matters.items() if o not in external_people}

    hours: dict[str, int] = defaultdict(int)
    staff: dict[str, set] = defaultdict(set)
    wip_cents: dict[str, int] = defaultdict(int)
    for ticket, person, seconds, rate, billable in clio.execute(
        "SELECT ticket_id, person, quantity_seconds, rate_cents, billable "
        "FROM activities"
    ):
        hours[ticket] += seconds
        staff[ticket].add(person)
        if billable and rate:
            wip_cents[ticket] += seconds * rate // 3600

    external = {
        p
        for (p,) in gmail.execute(
            "SELECT person_id FROM people WHERE affiliation='external'"
        )
    }
    threads: dict[str, list] = defaultdict(list)
    for row in gmail.execute(
        "SELECT message_id, thread_id, sender, time FROM messages "
        "ORDER BY time, message_id"
    ):
        threads[row[1]].append(row)
    # The client's oldest still-unanswered last word, per client.
    waiting_since: dict[str, int] = {}
    for thread in threads.values():
        last = thread[-1]
        if last[2] in external:
            waiting_since[last[2]] = min(waiting_since.get(last[2], last[3]), last[3])
    horizon = max((m[3] for t in threads.values() for m in t), default=0)

    rows = []
    for ticket in sorted(t for t in matters if t not in internal):
        _description, responsible, originator = matters[ticket]
        waiting = originator in waiting_since
        rows.append(
            {
                "ticket_id": ticket,
                "client_contact": names.get(originator, originator or ""),
                "responsible": names.get(responsible, responsible or ""),
                "total_hours": round(hours.get(ticket, 0) / 3600, 2),
                "staff_count": len(staff.get(ticket, ())),
                "status": "awaiting_firm_reply" if waiting else "clear",
                "client_waiting_hours": round(
                    (horizon - waiting_since[originator]) / 3600, 1
                )
                if waiting
                else 0.0,
                "wip_dollars": round(wip_cents.get(ticket, 0) / 100, 2),
            }
        )
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[row["status"]] += 1
    awaiting = [r for r in rows if r["status"] == "awaiting_firm_reply"]
    OUT.write_text(
        json.dumps(
            {
                "client_engagements": len(rows),
                "status_counts": dict(sorted(counts.items())),
                "awaiting_firm_reply": sorted(r["ticket_id"] for r in awaiting),
                "longest_waiting_engagement": max(
                    awaiting, key=lambda r: r["client_waiting_hours"]
                )["ticket_id"]
                if awaiting
                else None,
                "wip_at_risk_dollars": round(
                    sum(r["wip_dollars"] for r in awaiting), 2
                ),
                "at_risk_over_10k": sorted(
                    r["ticket_id"] for r in awaiting if r["wip_dollars"] > 10000
                ),
                "engagements": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
