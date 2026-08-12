#!/bin/sh
# Naive baseline: the crudest plausible single-surface pass. It opens every DM
# lane honestly, but reads the *first* reply from the person asked as the return
# (acknowledgements included), reads Slack only, and recognizes only two states
# -- back the same day or not. It never learned the next-working-day window, the
# federal holidays, the mail surface, or that "still have it up here" is not a
# return, so most rows land wrong even though it files a complete-looking ledger.
exec python3 - <<'PY'
import json
import os
import sqlite3
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

EPOCH = date(2026, 3, 2)
PACIFIC = ZoneInfo("America/Los_Angeles")
REQUEST = "do you still have the sign-in sheet from yesterday?"
# instruction.md scopes the sweep to March through June; a plausible shortcut
# still respects the stated period and errs on the follow-up window and the mail
# surface instead.
SCOPE_SECONDS = (date(2026, 7, 1) - EPOCH).days * 86_400
STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(sql, *params):
    with sqlite3.connect(f"file:{STATE}/slack.db?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(timestamp):
    return EPOCH + timedelta(days=timestamp // 86400)


def iso(timestamp):
    return (datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=timestamp)).isoformat()


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
    "SELECT conversation_id, sender, body, time, ts FROM messages "
    "WHERE time < ? ORDER BY time, ts",
    SCOPE_SECONDS,
):
    if lane in lanes:
        history.setdefault(lane, []).append((sender, body, timestamp, ts))

audit = []
for lane, messages in history.items():
    for position, (asker, body, timestamp, ts) in enumerate(messages):
        if body.strip().lower() != REQUEST:
            continue
        (asked_of,) = members[lane] - {asker}
        asked_on = day_of(timestamp)
        first = next(
            (
                (reply_time, reply_ts)
                for reply_sender, _, reply_time, reply_ts in messages[position + 1 :]
                if reply_sender == asked_of and reply_time > timestamp
            ),
            None,
        )
        same_day = first is not None and day_of(first[0]) == asked_on
        audit.append(
            {
                "request_ts": ts,
                "request_date": asked_on.isoformat(),
                "asked_by": names[asker],
                "asked_of": names[asked_of],
                "first_return_surface": "slack" if first else "none",
                "first_return_id": first[1] if first else "",
                "first_return_at": iso(first[0]) if first else "",
                "outcome": "same_day" if same_day else "unresolved",
            }
        )

audit.sort(key=lambda record: float(record["request_ts"]))
breach_audit = [record for record in audit if record["outcome"] != "same_day"]
breaches = [
    {
        "ts": record["request_ts"],
        "date": record["request_date"],
        "asked_by": record["asked_by"],
        "asked_of": record["asked_of"],
        "resolution": "unresolved",
    }
    for record in breach_audit
]
review = {
    "requests_reviewed": len(audit),
    "conversations_reviewed": len(history),
    "same_day_breach_ts": [request["ts"] for request in breaches],
    "same_day_breaches": breaches,
    "returned_same_day": len(audit) - len(breach_audit),
    "returned_next_working_day": 0,
    "unresolved_by_followup": len(breaches),
    "returned_next_working_day_ts": [],
    "unresolved_ts": [request["ts"] for request in breaches],
    "custody_audit": audit,
}
with open("visitor-log.json", "w") as handle:
    json.dump(review, handle, indent=2)
PY
