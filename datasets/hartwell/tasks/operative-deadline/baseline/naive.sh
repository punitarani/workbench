#!/bin/sh
# Naive baseline: trusts the written record in Gmail — the clerk's notices
# plus the June 16 internal docket recap that formally restates the last
# noticed date. Every email states a superseded date; the operative one
# exists only in a DM that public-channel search cannot reach.
exec python3 - << 'EOF'
import json
import re
import sqlite3

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
        found.append(f"2026-{MONTHS[month.lower()]:02d}-{int(day):02d}")
    return found

notices = rows(
    "gmail.db",
    "SELECT m.message_id, m.body FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%Arroyo%' "
    "AND lower(p.title) LIKE '%clerk%' ORDER BY m.time",
)
noticed = [max(dates_in(body)) for _, body in notices]
recap = rows(
    "gmail.db",
    "SELECT body FROM messages WHERE subject LIKE 'Docket recap%' "
    "ORDER BY time DESC",
)
# The latest formal mail agrees with the last notice, so treat it as
# confirmation and report the last noticed setting as operative.
assert recap and noticed[-1] in dates_in(recap[0][0])

deadline = {
    "operative_date": noticed[-1],
    "operative_time": "10:00",
    "correction_ts": None,
    "superseded_dates": noticed[:-1],
    "supersessions": [
        {"invalidated": noticed[index], "by": notices[index + 1][0]}
        for index in range(len(noticed) - 1)
    ],
    # The recap agrees with the last notice, so the naive read finds
    # nothing stale to flag.
    "stale_calendar_refs": [],
}
with open("deadline.json", "w") as handle:
    json.dump(deadline, handle, indent=2)
print("deadline.json written (last-written-notice assumption)")
EOF
