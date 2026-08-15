"""Reference solver: how fast the firm answers its clients.

A message counts as answered when someone inside the firm writes into
the same thread after it. Consecutive client messages are the trap: only
the firm's next message closes them, and it closes all of them at once.
"""

import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sla_report.json")


def _median(values: list[float]) -> float:
    ordered = sorted(values)
    middle = len(ordered) // 2
    if not ordered:
        return 0.0
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    external = {
        p
        for (p,) in gmail.execute(
            "SELECT person_id FROM people WHERE affiliation='external'"
        )
    }
    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    messages = list(
        gmail.execute(
            "SELECT message_id, thread_id, sender, time FROM messages "
            "ORDER BY time, message_id"
        )
    )
    threads: dict[str, list] = defaultdict(list)
    for row in messages:
        threads[row[1]].append(row)

    per_client: dict[str, dict] = defaultdict(
        lambda: {"inbound": 0, "answered": 0, "waits": [], "unanswered": []}
    )
    for thread in threads.values():
        for index, (message_id, _thread_id, sender, when) in enumerate(thread):
            if sender not in external:
                continue
            row = per_client[sender]
            row["inbound"] += 1
            reply = next((m for m in thread[index + 1 :] if m[2] not in external), None)
            if reply is None:
                row["unanswered"].append(message_id)
            else:
                row["answered"] += 1
                row["waits"].append((reply[3] - when) / 3600)

    clients = []
    for person, row in sorted(
        per_client.items(), key=lambda kv: names.get(kv[0], kv[0])
    ):
        clients.append(
            {
                "client": names.get(person, person),
                "inbound": row["inbound"],
                "answered": row["answered"],
                "unanswered_message_ids": sorted(row["unanswered"]),
                "median_reply_hours": round(_median(row["waits"]), 2),
                "longest_reply_hours": round(max(row["waits"]), 2)
                if row["waits"]
                else 0.0,
            }
        )
    all_waits = [w for row in per_client.values() for w in row["waits"]]
    OUT.write_text(
        json.dumps(
            {
                "clients": len(clients),
                "inbound_total": sum(c["inbound"] for c in clients),
                "unanswered_total": sum(
                    len(c["unanswered_message_ids"]) for c in clients
                ),
                "firm_median_reply_hours": round(_median(all_waits), 2),
                "slowest_client": max(clients, key=lambda c: c["longest_reply_hours"])[
                    "client"
                ],
                "client_rows": clients,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
