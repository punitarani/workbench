#!/bin/sh
# The same shortcut as naive.sh, carried through to the work product
# instead of stopping at the headline counts. naive.sh emits an empty
# response_audit, which is not a shortcut an agent would take -- it is
# the baseline declining to compete, and it makes this task look far
# more discriminating than it is. This file exists so the difference is
# measured rather than assumed. See test_the_honest_shortcut_nearly
# _reproduces_the_ledger.
exec python3 - << 'EOF'
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EPOCH = date(2026, 3, 2)
PACIFIC = ZoneInfo("America/Los_Angeles")
REQUEST = "mind taking a quick look at my draft before it goes out?"
# instruction.md scopes the sweep to March through June; a plausible
# shortcut still respects the stated period and errs on the deadline and
# the mail surface instead.
SCOPE_SECONDS = (date(2026, 7, 1) - EPOCH).days * 86_400

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
    "SELECT conversation_id, sender, body, time, ts FROM messages "
    "WHERE time < ? ORDER BY time",
    SCOPE_SECONDS,
):
    if conversation_id in pairs:
        chat.setdefault(conversation_id, []).append((sender, body, time, ts))

requests, unanswered = 0, []
same_day = 0
audit = []
for conversation_id, messages in chat.items():
    for position, (sender, body, time, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        requests += 1
        (asked_of,) = membership[conversation_id] - {sender}
        asked_on = day_of(time)
        reply = next(
            (
                (reply_time, reply_ts)
                for reply_sender, _, reply_time, reply_ts in messages[position + 1 :]
                if reply_sender == asked_of and day_of(reply_time) == asked_on
            ),
            None,
        )
        if reply is not None:
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
        # The same shortcut, carried through to the workpaper: the clock
        # stops at close of business and mail is never opened, so an
        # overnight pickup and the one mailed answer are recorded as
        # nothing having come back.
        audit.append(
            {
                "request_ts": ts,
                "request_date": asked_on.isoformat(),
                "asked_by": names[sender],
                "asked_of": names[asked_of],
                "first_response_at": (
                    datetime.fromtimestamp(int(float(reply[1])), PACIFIC).isoformat()
                    if reply
                    else ""
                ),
                "first_response_id": reply[1] if reply else "",
                "first_response_surface": "slack" if reply else "none",
                "outcome": "same_day" if reply else "unanswered",
            }
        )

review = {
    "requests_reviewed": requests,
    "conversations_reviewed": len(chat),
    "unanswered_request_ts": sorted(r["ts"] for r in unanswered),
    "unanswered_requests": sorted(unanswered, key=lambda r: r["date"]),
    "answered_same_day": same_day,
    "answered_next_working_day": 0,
    "unanswered_by_deadline": len(unanswered),
    "came_back_later": [],
    "unanswered_askers": sorted({r["asked_by"] for r in unanswered}),
    "response_audit": audit,
}
with open("second-read.json", "w") as handle:
    json.dump(review, handle, indent=2)
print("second-read.json written (same-day assumption)")
EOF
