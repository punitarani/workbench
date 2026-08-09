#!/bin/sh
# Reference solution: reads the clerk's notices from Gmail in order, then
# checks the firm's own record for anything that supersedes the last
# written notice — and finds the Slack correction that moved the hearing.
# Fails rather than answer from assumptions — if the correction is not in
# the record, the last notice must not be reported as operative.
exec python3 - << 'EOF'
import json
import re
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
MONTHS = {
    name: index + 1
    for index, name in enumerate(
        (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        )
    )
}

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def dates_in(text):
    found = []
    for month, day in re.findall(
        r"\b(January|February|March|April|May|June|July|August|September|"
        r"October|November|December)\s+(\d{1,2})\b",
        text,
    ):
        found.append(date(2026, MONTHS[month.lower()], int(day)))
    return found

notices = rows(
    "gmail.db",
    "SELECT m.body, m.time FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%Arroyo%' "
    "AND p.title LIKE '%clerk%' ORDER BY m.time",
)
if len(notices) < 3:
    sys.exit(f"expected three clerk notices in Gmail, found {len(notices)}")
noticed = []
for body, _ in notices:
    body_dates = dates_in(body)
    if not body_dates:
        sys.exit("a clerk notice states no hearing date")
    newly_set = max(body_dates)
    if noticed and newly_set <= noticed[-1]:
        sys.exit("clerk notices do not move the hearing forward")
    noticed.append(newly_set)

corrections = rows(
    "slack.db",
    "SELECT body, ts, time FROM messages WHERE body LIKE '%Fruitvale%' "
    "ORDER BY time",
)
last_notice_time = notices[-1][1]
operative = None
for body, ts, time in corrections:
    stated = [d for d in dates_in(body) if d not in noticed]
    if time > last_notice_time and stated and "wrong date" in body:
        clock = re.search(r"\b(\d{1,2}):(\d{2})\b", body)
        if clock is None:
            sys.exit("the correction states no hearing time")
        operative = (
            max(stated),
            f"{int(clock.group(1)):02d}:{clock.group(2)}",
            ts,
        )
if operative is None:
    sys.exit(
        "no record supersedes the clerk's last notice; refusing to report "
        "a stale date as operative"
    )

deadline = {
    "operative_date": operative[0].isoformat(),
    "operative_time": operative[1],
    "correction_ts": operative[2],
    "superseded_dates": [d.isoformat() for d in noticed],
}
with open("deadline.json", "w") as handle:
    json.dump(deadline, handle, indent=2)
print("deadline.json written")
EOF
