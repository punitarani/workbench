#!/bin/sh
# Naive baseline: the honest single-surface pass. It enforces the same-day
# deadline in every DM lane but treats every breach as unresolved because it
# never checks the next-working-day Slack window or directed mail.
exec python3 - <<'PY'
import json
import os
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
REQUEST = "do you still have the sign-in sheet from yesterday?"
STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(sql):
    with sqlite3.connect(f"file:{STATE}/slack.db?mode=ro", uri=True) as connection:
        return connection.execute(sql).fetchall()


def day_of(timestamp):
    return EPOCH + timedelta(days=timestamp // 86400)


names = dict(rows("SELECT person_id, name FROM people"))
lanes = {
    lane
    for (lane,) in rows("SELECT conversation_id FROM conversations WHERE kind='dm'")
}
members = {}
for lane, person in rows("SELECT conversation_id, person_id FROM members"):
    members.setdefault(lane, set()).add(person)
history = {}
for lane, sender, body, timestamp, ts in rows(
    "SELECT conversation_id, sender, body, time, ts FROM messages ORDER BY time"
):
    if lane in lanes:
        history.setdefault(lane, []).append((sender, body, timestamp, ts))

requests = []
for lane, messages in history.items():
    for position, (asker, body, timestamp, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        (asked_of,) = members[lane] - {asker}
        asked_on = day_of(timestamp)
        same_day = any(
            sender == asked_of and day_of(reply_time) == asked_on
            for sender, _, reply_time, _ in messages[position + 1 :]
        )
        requests.append(
            {
                "ts": ts,
                "date": asked_on.isoformat(),
                "asked_by": names[asker],
                "asked_of": names[asked_of],
                "resolution": "same_day" if same_day else "unresolved",
            }
        )

breaches = [request for request in requests if request["resolution"] == "unresolved"]
review = {
    "requests_reviewed": len(requests),
    "conversations_reviewed": len(history),
    "same_day_breach_ts": [request["ts"] for request in breaches],
    "same_day_breaches": breaches,
    "returned_same_day": len(requests) - len(breaches),
    "returned_next_working_day_ts": [],
    "unresolved_ts": [request["ts"] for request in breaches],
}
with open("visitor-log.json", "w") as handle:
    json.dump(review, handle, indent=2)
PY
