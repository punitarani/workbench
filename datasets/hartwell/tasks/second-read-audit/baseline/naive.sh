#!/bin/sh
# Naive baseline: the plausible single-source path. It opens every
# one-to-one conversation honestly — the counts come out right — but stops
# the clock at close of business on the day of the request and never looks
# at mail, so the overnight pickups and the one mailed answer land on the
# list as exceptions.
exec python3 - << 'EOF'
import json
import os
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
REQUEST = "mind taking a quick look at my draft before it goes out?"

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time):
    return EPOCH + timedelta(days=time // 86400)


names = dict(rows("slack.db", "SELECT person_id, name FROM people"))
pairs = {
    conversation_id
    for (conversation_id,) in rows(
        "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
    )
}
membership = {}
for conversation_id, person in rows(
    "slack.db", "SELECT conversation_id, person_id FROM members"
):
    membership.setdefault(conversation_id, set()).add(person)
chat = {}
for conversation_id, sender, body, time, ts in rows(
    "slack.db",
    "SELECT conversation_id, sender, body, time, ts FROM messages ORDER BY time",
):
    if conversation_id in pairs:
        chat.setdefault(conversation_id, []).append((sender, body, time, ts))

requests, unanswered = 0, []
same_day = 0
for conversation_id, messages in chat.items():
    for position, (sender, body, time, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        requests += 1
        (asked_of,) = membership[conversation_id] - {sender}
        asked_on = day_of(time)
        answered = any(
            reply_sender == asked_of and day_of(reply_time) == asked_on
            for reply_sender, _, reply_time, _ in messages[position + 1 :]
        )
        if answered:
            same_day += 1
        else:
            unanswered.append(
                {
                    "ts": ts,
                    "date": asked_on.isoformat(),
                    "asked_by": names[sender],
                    "asked_of": names[asked_of],
                }
            )

review = {
    "requests_reviewed": requests,
    "conversations_reviewed": len(chat),
    "unanswered_request_ts": sorted(r["ts"] for r in unanswered),
    "unanswered_requests": sorted(unanswered, key=lambda r: r["date"]),
    "answered_same_day": same_day,
    "came_back_later": [],
    "unanswered_askers": sorted({r["asked_by"] for r in unanswered}),
}
with open("second-read.json", "w") as handle:
    json.dump(review, handle, indent=2)
print("second-read.json written (same-day assumption)")
EOF
