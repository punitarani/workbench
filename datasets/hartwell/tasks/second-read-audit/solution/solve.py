"""Reference oracle for second-read-audit; emits the certified deliverable on stdout."""

import json
import os
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
REQUEST = "mind taking a quick look at my draft before it goes out?"

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time):
    return EPOCH + timedelta(days=time // 86400)


def next_working_day(day):
    moment = day + timedelta(days=1)
    while moment.weekday() >= 5:
        moment += timedelta(days=1)
    return moment


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
if len(chat) < 10:
    sys.exit(f"expected the firm's one-to-one conversations, found {len(chat)}")

# Directed mail: who wrote to whom, on which day.
recipients = {}
for message_id, person in rows(
    "gmail.db", "SELECT message_id, person_id FROM recipients"
):
    recipients.setdefault(message_id, set()).add(person)
mailed = {
    (sender, recipient, day_of(time))
    for message_id, sender, time in rows(
        "gmail.db", "SELECT message_id, sender, time FROM messages"
    )
    for recipient in recipients.get(message_id, ())
}

requests = []
for conversation_id, messages in chat.items():
    for position, (sender, body, time, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        (asked_of,) = membership[conversation_id] - {sender}
        asked_on = day_of(time)
        replies = {
            day_of(reply_time)
            for reply_sender, _, reply_time, _ in messages[position + 1 :]
            if reply_sender == asked_of
        }
        window = {asked_on, next_working_day(asked_on)}
        requests.append(
            {
                "ts": ts,
                "date": asked_on.isoformat(),
                "asked_by": names[sender],
                "asked_of": names[asked_of],
                "same_day": asked_on in replies,
                "in_window": bool(replies & window)
                or any((asked_of, sender, moment) in mailed for moment in window),
            }
        )
if len(requests) < 50:
    sys.exit(f"expected a dense request fabric, found {len(requests)}")

unanswered = [r for r in requests if not r["in_window"]]
if not 3 <= len(unanswered) <= 8:
    sys.exit(f"expected a small unanswered set, found {len(unanswered)}")
later = [r for r in requests if r["in_window"] and not r["same_day"]]
if len(later) < 3:
    sys.exit(f"expected overnight pickups to decoy a same-day reading, {len(later)}")
if len({r["asked_by"] for r in unanswered}) < 3:
    sys.exit("expected the unanswered requests to span several askers")

review = {
    "requests_reviewed": len(requests),
    "conversations_reviewed": len(chat),
    "unanswered_request_ts": sorted(r["ts"] for r in unanswered),
    "unanswered_requests": [
        {
            "ts": r["ts"],
            "date": r["date"],
            "asked_by": r["asked_by"],
            "asked_of": r["asked_of"],
        }
        for r in sorted(unanswered, key=lambda r: r["date"])
    ],
    "answered_same_day": sum(1 for r in requests if r["same_day"]),
    "came_back_later": sorted(r["ts"] for r in later),
    "unanswered_askers": sorted({r["asked_by"] for r in unanswered}),
}
json.dump(review, sys.stdout, indent=2)
sys.stdout.write("\n")
