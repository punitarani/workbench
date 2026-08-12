"""Reference oracle for second-read-audit; emits the certified deliverable on stdout."""

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EPOCH = date(2026, 3, 2)
REQUEST = "mind taking a quick look at my draft before it goes out?"
PACIFIC = ZoneInfo("America/Los_Angeles")
CUTOFF = (date(2026, 7, 1) - EPOCH).days * 86_400

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


def iso(time):
    return (datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=time)).isoformat()


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
    "SELECT conversation_id, sender, body, time, ts FROM messages "
    "WHERE time < ? ORDER BY time",
    CUTOFF,
):
    if conversation_id in pairs:
        chat.setdefault(conversation_id, []).append((sender, body, time, ts))
if len(chat) < 10:
    sys.exit(f"expected the firm's one-to-one conversations, found {len(chat)}")

# Directed mail: who wrote to whom, with exact source identity and time.
recipients = {}
for message_id, person in rows(
    "gmail.db", "SELECT message_id, person_id FROM recipients"
):
    recipients.setdefault(message_id, set()).add(person)
mailed = [
    (sender, recipient, time, message_id)
    for message_id, sender, time in rows(
        "gmail.db",
        "SELECT message_id, sender, time FROM messages WHERE time < ?",
        CUTOFF,
    )
    for recipient in recipients.get(message_id, ())
]

requests = []
for conversation_id, messages in chat.items():
    for position, (sender, body, time, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        (asked_of,) = membership[conversation_id] - {sender}
        asked_on = day_of(time)
        candidates = [
            (reply_time, "slack", reply_ts)
            for reply_sender, _, reply_time, reply_ts in messages[position + 1 :]
            if reply_sender == asked_of and reply_time > time
        ]
        candidates.extend(
            (mail_time, "gmail", message_id)
            for mail_sender, recipient, mail_time, message_id in mailed
            if mail_sender == asked_of and recipient == sender and mail_time > time
        )
        first = min(candidates, default=None)
        deadline = next_working_day(asked_on)
        if first is None:
            outcome = "unanswered"
        elif day_of(first[0]) == asked_on:
            outcome = "same_day"
        elif day_of(first[0]) <= deadline:
            outcome = "next_working_day"
        else:
            outcome = "unanswered"
        requests.append(
            {
                "ts": ts,
                "date": asked_on.isoformat(),
                "asked_by": names[sender],
                "asked_of": names[asked_of],
                "first_response_surface": first[1] if first else "none",
                "first_response_id": first[2] if first else "",
                "first_response_at": iso(first[0]) if first else "",
                "outcome": outcome,
            }
        )
if len(requests) < 50:
    sys.exit(f"expected a dense request fabric, found {len(requests)}")

unanswered = [r for r in requests if r["outcome"] == "unanswered"]
if not 3 <= len(unanswered) <= 8:
    sys.exit(f"expected a small unanswered set, found {len(unanswered)}")
later = [r for r in requests if r["outcome"] == "next_working_day"]
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
    "answered_same_day": sum(1 for r in requests if r["outcome"] == "same_day"),
    "answered_next_working_day": len(later),
    "unanswered_by_deadline": len(unanswered),
    "came_back_later": sorted(r["ts"] for r in later),
    "unanswered_askers": sorted({r["asked_by"] for r in unanswered}),
    "response_audit": [
        {
            "request_ts": r["ts"],
            "request_date": r["date"],
            "asked_by": r["asked_by"],
            "asked_of": r["asked_of"],
            "first_response_surface": r["first_response_surface"],
            "first_response_id": r["first_response_id"],
            "first_response_at": r["first_response_at"],
            "outcome": r["outcome"],
        }
        for r in sorted(requests, key=lambda item: float(item["ts"]))
    ],
}
json.dump(review, sys.stdout, indent=2)
sys.stdout.write("\n")
