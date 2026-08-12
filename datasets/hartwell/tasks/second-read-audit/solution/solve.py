"""Reference oracle for second-read-audit; emits the certified deliverable on stdout.

Nothing here is a table of answers. Every row's outcome is DERIVED from the
record: the request instants are read from the one-to-one DMs, the reviewer's
*read* is located by parsing the reply prose (a message counts as the read only
when it delivers a verdict on the draft — a review marker in chat, or a
directed "Draft read" email — never a bare acknowledgement), each read is
matched to the request instance it answers by timing across surfaces, and the
outcome (same_day / next_working_day / unanswered) falls out of the Pacific
calendar date of that first read against a holiday-aware next-working-day
deadline. Timestamps are stored as machine seconds; the day boundaries are
Pacific, so an evening read is still the same working day even though its UTC
date is the next one.
"""

import json
import os
import sqlite3
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EPOCH = date(2026, 3, 2)
PACIFIC = ZoneInfo("America/Los_Angeles")
REQUEST = "mind taking a quick look at my draft before it goes out?"
CUTOFF = (date(2026, 7, 1) - EPOCH).days * 86_400

# A reply is the *read* only if it delivers a verdict on the draft. In chat the
# verdict carries one of these verbatim markers; ordinary acknowledgements
# ("got it, I'll look tonight") and chatter carry none and are not the read.
REVIEW_MARKERS = (
    "send it out",
    "good to go",
    "one redline",
    "ready to go out",
    "no changes from me",
    "ship it",
    "clear to file",
    "signed off on the draft",
)
# A directed email is a cross-surface read iff its subject carries this marker.
EMAIL_MARKER = "draft read"

# Federal holidays that fall on a weekday inside the March-June review window;
# the firm treats them as non-working days when computing the deadline.
HOLIDAYS = frozenset({date(2026, 5, 25), date(2026, 6, 19)})

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time):
    return EPOCH + timedelta(days=time // 86400)


def is_workday(day):
    return day.weekday() < 5 and day not in HOLIDAYS


def next_working_day(day):
    moment = day + timedelta(days=1)
    while not is_workday(moment):
        moment += timedelta(days=1)
    return moment


def iso(time):
    return (datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=time)).isoformat()


def is_review(body):
    lowered = body.lower()
    return any(marker in lowered for marker in REVIEW_MARKERS)


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

# Directed mail: sender, recipient, time, message_id, and subject, so a
# "Draft read" return can be recognized and matched to its asker.
recipients = {}
for message_id, person in rows(
    "gmail.db", "SELECT message_id, person_id FROM recipients"
):
    recipients.setdefault(message_id, set()).add(person)
mailed = []
for message_id, sender, subject, time in rows(
    "gmail.db",
    "SELECT message_id, sender, subject, time FROM messages WHERE time < ?",
    CUTOFF,
):
    for recipient in recipients.get(message_id, ()):
        mailed.append((sender, recipient, time, message_id, subject))

# Every second-read request, with its asker, reviewer, and instant.
requests = []
for conversation_id, messages in chat.items():
    members = membership[conversation_id]
    if len(members) != 2:
        continue
    for sender, body, time, ts in messages:
        if body.strip().lower() != REQUEST:
            continue
        (reviewer,) = members - {sender}
        requests.append(
            {
                "conversation_id": conversation_id,
                "ts": ts,
                "time": time,
                "asked_by": sender,
                "asked_of": reviewer,
            }
        )
if len(requests) < 50:
    sys.exit(f"expected a dense request fabric, found {len(requests)}")

# Every reviewer read, as (time, surface, id, asker, reviewer). A chat read is
# a verdict-bearing DM; its asker is the other lane member. An email read is a
# "Draft read" directed message; its asker is the recipient.
reads = []
for conversation_id, messages in chat.items():
    members = membership[conversation_id]
    if len(members) != 2:
        continue
    for sender, body, time, ts in messages:
        if is_review(body):
            (asker,) = members - {sender}
            reads.append((time, "slack", ts, asker, sender))
for sender, recipient, time, message_id, subject in mailed:
    if EMAIL_MARKER in subject.lower():
        reads.append((time, "gmail", message_id, recipient, sender))

# Match each read to the request instance it answers: the latest request from
# the same asker to the same reviewer that precedes it. A read whose asker
# re-sent the request answers the re-sent instance, leaving the original with
# only its acknowledgement.
by_pair = {}
for index, request in enumerate(requests):
    by_pair.setdefault((request["asked_by"], request["asked_of"]), []).append(index)
for indices in by_pair.values():
    indices.sort(key=lambda index: requests[index]["time"])
for request in requests:
    request["read"] = None
for time, surface, identifier, asker, reviewer in sorted(reads):
    owner = None
    for index in by_pair.get((asker, reviewer), ()):
        if requests[index]["time"] < time:
            owner = index
    if owner is None:
        continue
    current = requests[owner]["read"]
    if current is None or time < current[0]:
        requests[owner]["read"] = (time, surface, identifier)

# Classify each request against the holiday-aware deadline.
records = []
for request in requests:
    asked_on = day_of(request["time"])
    deadline = next_working_day(asked_on)
    read = request["read"]
    if read is None:
        outcome, surface, identifier, at = "unanswered", "none", "", ""
    else:
        read_time, surface, identifier = read
        at = iso(read_time)
        read_day = day_of(read_time)
        if read_day == asked_on:
            outcome = "same_day"
        elif read_day <= deadline:
            outcome = "next_working_day"
        else:
            outcome = "unanswered"
    records.append(
        {
            "ts": request["ts"],
            "date": asked_on.isoformat(),
            "asked_by": names[request["asked_by"]],
            "asked_of": names[request["asked_of"]],
            "first_response_surface": surface,
            "first_response_id": identifier,
            "first_response_at": at,
            "outcome": outcome,
        }
    )

unanswered = [r for r in records if r["outcome"] == "unanswered"]
if not 5 <= len(unanswered) <= 15:
    sys.exit(f"expected a small unanswered set, found {len(unanswered)}")
later = [r for r in records if r["outcome"] == "next_working_day"]
if len(later) < 3:
    sys.exit(f"expected overnight pickups to decoy a same-day reading, {len(later)}")
if len({r["asked_by"] for r in unanswered}) < 3:
    sys.exit("expected the unanswered requests to span several askers")

review = {
    "requests_reviewed": len(records),
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
    "answered_same_day": sum(1 for r in records if r["outcome"] == "same_day"),
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
        for r in sorted(records, key=lambda item: float(item["ts"]))
    ],
}
json.dump(review, sys.stdout, indent=2)
sys.stdout.write("\n")
