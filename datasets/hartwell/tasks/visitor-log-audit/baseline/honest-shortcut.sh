#!/bin/sh
# The plausible surface reading, carried all the way through the work product:
# count the first reply back from the person asked (acknowledgements included,
# so "still have it up here" is read as if the sheet were returned), read Slack
# only, date timestamps by the stored Pacific clock, and skip weekends but not
# holidays when computing the follow-up deadline. That is exactly the reading
# the arc is built to punish -- the acknowledgement-then-return gap, the
# cross-surface mail returns, the holiday-skipped deadlines, and the re-sent
# request now cost it most of its credit (~0.24, far below the certified 1.0),
# which this file exists to measure rather than assume. See
# test_the_honest_shortcut_loses_most_of_the_ledger.
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
# still respects the stated period and errs on the acknowledgement gap, the
# mail surface, and the holiday-skipped deadline instead.
SCOPE_SECONDS = (date(2026, 7, 1) - EPOCH).days * 86_400
STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(sql, *params):
    with sqlite3.connect(f"file:{STATE}/slack.db?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(timestamp):
    return EPOCH + timedelta(days=timestamp // 86400)


def next_working_day(day):
    # Weekends only -- the shortcut never learned the federal holidays.
    day += timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


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
        # The first reply back from the person asked, acknowledgements included.
        first = next(
            (
                (reply_time, reply_ts)
                for reply_sender, _, reply_time, reply_ts in messages[position + 1 :]
                if reply_sender == asked_of and reply_time > timestamp
            ),
            None,
        )
        if first is None:
            outcome = "unresolved"
        else:
            return_day = day_of(first[0])
            if return_day == asked_on:
                outcome = "same_day"
            elif return_day <= next_working_day(asked_on):
                outcome = "next_working_day"
            else:
                outcome = "unresolved"
        audit.append(
            {
                "request_ts": ts,
                "request_date": asked_on.isoformat(),
                "asked_by": names[asker],
                "asked_of": names[asked_of],
                "first_return_surface": "slack" if first else "none",
                "first_return_id": first[1] if first else "",
                "first_return_at": iso(first[0]) if first else "",
                "outcome": outcome,
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
        "resolution": record["outcome"],
    }
    for record in breach_audit
]
returned_next = [r["ts"] for r in breaches if r["resolution"] == "next_working_day"]
unresolved = [r["ts"] for r in breaches if r["resolution"] == "unresolved"]
review = {
    "requests_reviewed": len(audit),
    "conversations_reviewed": len(history),
    "same_day_breach_ts": [request["ts"] for request in breaches],
    "same_day_breaches": breaches,
    "returned_same_day": len(audit) - len(breach_audit),
    "returned_next_working_day": len(returned_next),
    "unresolved_by_followup": len(unresolved),
    "returned_next_working_day_ts": returned_next,
    "unresolved_ts": unresolved,
    "custody_audit": audit,
}
with open("visitor-log.json", "w") as handle:
    json.dump(review, handle, indent=2)
PY
