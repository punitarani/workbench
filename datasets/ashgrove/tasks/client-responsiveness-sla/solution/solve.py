"""Reference solver: how fast the firm answers its clients, thread by thread.

A message counts as answered when someone inside the firm writes into the
same thread after it. Consecutive client messages are the trap: only the
firm's next message closes them, and it closes all of them at once.

Reported per conversation rather than per client. Nine clients make nine
rows, and a nine-row answer is graded as a verdict on the rule — every
rollout of the per-client version came back exactly 1.000. A practice
manager reads this thread by thread anyway: the question is which
conversation is sitting unanswered, not which client is on average slow.
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
    # Outside the firm is not the same as a client: the peer reviewer writes
    # in too, and the directory says which is which. Everyone external still
    # counts as "not the firm" for the purpose of who answers whom.
    external = {
        p
        for (p,) in gmail.execute(
            "SELECT person_id FROM people WHERE affiliation='external'"
        )
    }
    clients = {
        p
        for (p,) in gmail.execute(
            "SELECT person_id FROM people "
            "WHERE affiliation='external' AND department='Client'"
        )
    }
    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    threads: dict[str, list] = defaultdict(list)
    for row in gmail.execute(
        "SELECT message_id, thread_id, sender, time FROM messages "
        "ORDER BY time, message_id"
    ):
        threads[row[1]].append(row)

    rows = []
    all_waits: list[float] = []
    for thread_id, thread in sorted(threads.items()):
        inbound = [m for m in thread if m[2] in clients]
        if not inbound:
            continue
        unanswered = 0
        waits: list[float] = []
        for index, (_message_id, _t, _sender, when) in enumerate(thread):
            if thread[index][2] not in clients:
                continue
            reply = next((m for m in thread[index + 1 :] if m[2] not in external), None)
            if reply is None:
                unanswered += 1
            else:
                waits.append((reply[3] - when) / 3600)
        all_waits.extend(waits)
        rows.append(
            {
                "thread_id": thread_id,
                "client": names.get(inbound[0][2], inbound[0][2]),
                "messages": len(thread),
                "inbound": len(inbound),
                "unanswered": unanswered,
                "first_reply_hours": round(waits[0], 2) if waits else 0.0,
                "longest_reply_hours": round(max(waits), 2) if waits else 0.0,
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "threads_reviewed": len(threads),
                "threads_with_client_inbound": len(rows),
                "inbound_total": sum(row["inbound"] for row in rows),
                "unanswered_total": sum(row["unanswered"] for row in rows),
                "firm_median_reply_hours": round(_median(all_waits), 2),
                "slowest_thread": max(
                    rows, key=lambda row: (row["longest_reply_hours"], row["thread_id"])
                )["thread_id"]
                if rows
                else "",
                "threads": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
