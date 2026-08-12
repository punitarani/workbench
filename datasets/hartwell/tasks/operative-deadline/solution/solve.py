"""Reference oracle for the operative-deadline audit.

The certified deliverable is emitted on stdout.
"""

import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
MONTHS = {
    name: index + 1
    for index, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    )
}

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time):
    return EPOCH + timedelta(days=time // 86400)


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
    "SELECT m.message_id, m.body, m.time FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%Arroyo%' "
    "AND lower(p.title) LIKE '%clerk%' ORDER BY m.time",
)
if len(notices) < 3:
    sys.exit(f"expected three clerk notices in Gmail, found {len(notices)}")
noticed = []
for _, body, _ in notices:
    body_dates = dates_in(body)
    if not body_dates:
        sys.exit("a clerk notice states no hearing date")
    newly_set = max(body_dates)
    if noticed and newly_set <= noticed[-1]:
        sys.exit("clerk notices do not move the hearing forward")
    noticed.append(newly_set)

# The matter's Clio display number is the only handle the firm's own
# record uses when it talks about this file outside the case caption.
matter = rows(
    "clio.db",
    "SELECT display_number FROM matters WHERE description LIKE '%Arroyo%'",
)
if len(matter) != 1:
    sys.exit(f"expected one Arroyo matter in Clio, found {len(matter)}")
number = matter[0][0].split("-")[0]

last_notice_time = notices[-1][2]
last_day = noticed[-1].day
candidates = rows(
    "slack.db",
    "SELECT m.body, m.ts, m.time, c.kind FROM messages m "
    "JOIN conversations c ON c.conversation_id = m.conversation_id "
    "WHERE m.time > ? AND m.body LIKE ? ORDER BY m.time",
    last_notice_time,
    f"%{number}%",
)
operative = None
for body, ts, time, kind in candidates:
    negated = re.search(r"not the (\d{1,2})(?:st|nd|rd|th)\b", body)
    clock = re.search(r"\bat (\d{1,2})(?::(\d{2}))?\b", body)
    stated = [
        int(day)
        for day in re.findall(r"\bthe (\d{1,2})(?:st|nd|rd|th)\b", body)
        if int(day) != last_day
    ]
    if negated is None or int(negated.group(1)) != last_day:
        continue
    if clock is None:
        sys.exit("the correction states no hearing time")
    if not stated:
        sys.exit("the correction contradicts the notice but sets no date")
    if kind != "dm":
        sys.exit("the correction was expected outside public-channel reach")
    when = day_of(time)
    moved_to = date(when.year, when.month, stated[0])
    if moved_to <= when:
        sys.exit("the corrected date does not lie ahead of the correction")
    operative = (
        moved_to,
        f"{int(clock.group(1)):02d}:{clock.group(2) or '00'}",
        ts,
        time,
    )
if operative is None:
    sys.exit(
        "no record supersedes the clerk's last notice; refusing to report "
        "a stale date as operative"
    )
if operative[0] <= noticed[-1]:
    sys.exit("the correction does not move the hearing past the last notice")

supersessions = [
    {"invalidated": noticed[index].isoformat(), "by": notices[index + 1][0]}
    for index in range(len(noticed) - 1)
]
supersessions.append({"invalidated": noticed[-1].isoformat(), "by": operative[2]})

# The notice audit: every communication in the matter that names a
# hearing date, classified against the date that was operative when it
# was sent. One row per (message, date named) -- the notice that moves
# the hearing names both the date it retires and the date it sets, and
# the audit records each judgement separately.
MONTH_NAMES = {index: name for name, index in MONTHS.items()}
# The correction never spells the case name; it cites the matter by its
# Clio number, so the number is as much a handle on this file as the
# caption is.
TOKENS = ("arroyo", "dept. 511", "fruitvale", number.lower())
# A superseding instrument speaks for itself: it is operative from its own
# timestamp, so the notice announcing a move reports the new date rather
# than citing a stale one.
timeline = [
    (notices[0][2], noticed[0]),
    (notices[1][2], noticed[1]),
    (notices[2][2], noticed[2]),
    (operative[3], operative[0]),
]
instruments = {notices[1][0], notices[2][0], operative[2]}
cutovers = {
    noticed[0]: notices[1][2],
    noticed[1]: notices[2][2],
    noticed[2]: operative[3],
}


def forms_of(day):
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(
        day.day if day.day < 20 else day.day % 10, "th"
    )
    return (f"{MONTH_NAMES[day.month]} {day.day}".lower(), f"the {day.day}{suffix}")


def operative_when(time):
    settled = None
    for when, day in timeline:
        if time >= when:
            settled = day
    return settled


surfaces = [
    (message_id, "gmail", (subject + " " + body).lower(), time)
    for message_id, subject, body, time in rows(
        "gmail.db", "SELECT message_id, subject, body, time FROM messages"
    )
] + [
    (ts, "slack", body.lower(), time)
    for ts, body, time in rows("slack.db", "SELECT ts, body, time FROM messages")
]
hearing_dates = [*noticed, operative[0]]
audit = []
for identity, surface, text, time in surfaces:
    if not any(token in text for token in TOKENS):
        continue
    if time < timeline[0][0]:
        # Before the first notice the hearing had no setting, so no
        # message can cite one.
        continue
    for day in hearing_dates:
        hit_forms = [form for form in forms_of(day) if form in text]
        if not hit_forms:
            continue
        settled = operative_when(time)
        if identity in instruments or any(f"not {form}" in text for form in hit_forms):
            verdict = "correction"
        elif day == settled:
            verdict = "current"
        elif day in cutovers and time > cutovers[day]:
            verdict = "stale"
        else:
            sys.exit(
                f"{identity} cites {day} before it was ever set; the audit "
                "has no honest classification for that"
            )
        audit.append(
            {
                "time": time,
                "message_id": identity,
                "surface": surface,
                "cites_date": day.isoformat(),
                "operative_when_sent": settled.isoformat(),
                "classification": verdict,
            }
        )
audit.sort(key=lambda row: (row["time"], row["message_id"], row["cites_date"]))
for row in audit:
    del row["time"]

stale = [row["message_id"] for row in audit if row["classification"] == "stale"]
if len(stale) != 5:
    sys.exit(f"expected exactly five stale citations, found {stale}")
if {row["cites_date"] for row in audit if row["classification"] == "stale"} != {
    day.isoformat() for day in noticed
}:
    sys.exit("every superseded date must have at least one stale citation")
if not any(row["classification"] == "current" for row in audit):
    sys.exit("an audit with no current citation has lost the timeline")

deadline = {
    "operative_date": operative[0].isoformat(),
    "operative_time": operative[1],
    "correction_ts": operative[2],
    "superseded_dates": [d.isoformat() for d in noticed],
    "supersessions": supersessions,
    "stale_calendar_refs": stale,
    "notice_audit": audit,
}
json.dump(deadline, sys.stdout, indent=2)
sys.stdout.write("\n")
