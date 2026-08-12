#!/bin/sh
# Naive baseline: trusts the written record in Gmail — the clerk's notices
# plus the June 16 internal docket recap that formally restates the last
# noticed date. Every email states a superseded date; the operative one
# exists only in a DM that public-channel search cannot reach.
exec python3 - << 'EOF'
import json
import os
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

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
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

# The audit is built the same way the oracle builds it, but over Gmail
# alone and against a timeline that ends at the last written notice. The
# shortcut is the surface, not the method: every judgement below is
# correct given a record that never saw the DM.
TOKENS = ("arroyo", "dept. 511", "fruitvale")
notice_times = rows(
    "gmail.db",
    "SELECT m.time FROM messages m JOIN people p ON p.person_id = m.sender "
    "WHERE m.subject LIKE '%Arroyo%' AND lower(p.title) LIKE '%clerk%' "
    "ORDER BY m.time",
)
timeline = [(when, noticed[index]) for index, (when,) in enumerate(notice_times)]
instruments = {message_id for message_id, _ in notices[1:]}
cutovers = {noticed[index]: timeline[index + 1][0] for index in range(len(noticed) - 1)}


def forms_of(day):
    number = int(day.split("-")[2])
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        number if number < 20 else number % 10, "th"
    )
    month = [name for name, index in MONTHS.items() if index == int(day.split("-")[1])]
    return (f"{month[0]} {number}", f"the {number}{suffix}")


def operative_when(when):
    settled = None
    for moment, day in timeline:
        if when >= moment:
            settled = day
    return settled


audit = []
for message_id, subject, body, when in rows(
    "gmail.db", "SELECT message_id, subject, body, time FROM messages ORDER BY time"
):
    text = (subject + " " + body).lower()
    if not any(token in text for token in TOKENS) or when < timeline[0][0]:
        continue
    for day in noticed:
        hits = [form for form in forms_of(day) if form in text]
        if not hits:
            continue
        settled = operative_when(when)
        if message_id in instruments or any(f"not {form}" in text for form in hits):
            verdict = "correction"
        elif day == settled:
            verdict = "current"
        elif day in cutovers and when > cutovers[day]:
            verdict = "stale"
        else:
            continue
        audit.append(
            {
                "message_id": message_id,
                "surface": "gmail",
                "cites_date": day,
                "operative_when_sent": settled,
                "classification": verdict,
            }
        )

deadline = {
    "operative_date": noticed[-1],
    "operative_time": "10:00",
    "correction_ts": "",
    "superseded_dates": noticed[:-1],
    "supersessions": [
        {"invalidated": noticed[index], "by": notices[index + 1][0]}
        for index in range(len(noticed) - 1)
    ],
    "stale_calendar_refs": [
        row["message_id"] for row in audit if row["classification"] == "stale"
    ],
    "notice_audit": audit,
}
with open("deadline.json", "w") as handle:
    json.dump(deadline, handle, indent=2)
print("deadline.json written (last-written-notice assumption)")
EOF
