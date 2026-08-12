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

MONTH_NAMES = {index: name for name, index in MONTHS.items()}

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

# The firm dockets from the first reliable report, not the written
# confirmation. One reset was phoned through by the clerk and relayed in
# chat days before the notice arrived; that relay is the instrument, and
# it moves the date's cutover earlier -- which is what makes the mentions
# in between stale rather than current.
reported = {}
for body, ts, time, _kind in rows(
    "slack.db",
    "SELECT m.body, m.ts, m.time, c.kind FROM messages m JOIN conversations c "
    "ON c.conversation_id = m.conversation_id ORDER BY m.time",
):
    text = body.lower()
    if not any(token in text for token in ("arroyo", "dept. 511", "fruitvale")):
        continue
    if "vacated" not in text and "resetting" not in text:
        continue
    for index, day in enumerate(noticed[:-1]):
        # The relay has to retire a date the court had already noticed and
        # name the one that replaces it, and it only counts while that
        # date is still the operative setting.
        retires = any(form in text for form in (f"the {day.day}th", f"the {day.day}"))
        sets_next = any(
            form in text
            for form in (
                f"{MONTH_NAMES[noticed[index + 1].month]} {noticed[index + 1].day}",
                f"the {noticed[index + 1].day}th",
            )
        )
        if retires and sets_next and notices[index][2] < time < notices[index + 1][2]:
            reported.setdefault(day, (notices[index + 1][0], time))
            reported[day] = (ts, time)

supersessions = []
for index in range(len(noticed) - 1):
    day = noticed[index]
    instrument = reported.get(day, (notices[index + 1][0], notices[index + 1][2]))[0]
    supersessions.append({"invalidated": day.isoformat(), "by": instrument})
supersessions.append({"invalidated": noticed[-1].isoformat(), "by": operative[2]})

# The notice audit: every communication in the matter that names a
# hearing date, classified against the date that was operative when it
# was sent. One row per (message, date named) -- the notice that moves
# the hearing names both the date it retires and the date it sets, and
# the audit records each judgement separately.
# The correction never spells the case name; it cites the matter by its
# Clio number, so the number is as much a handle on this file as the
# caption is.
TOKENS = ("arroyo", "dept. 511", "fruitvale", number.lower())


def settled_at(index):
    """When noticed[index] stopped being the setting.

    The written notice unless the reset was phoned through first, in
    which case the relay controls and the date died days earlier.
    """

    if index + 1 >= len(noticed):
        return operative[3]
    return reported.get(noticed[index], (None, notices[index + 1][2]))[1]


# A superseding instrument speaks for itself: it is operative from its own
# timestamp, so the notice announcing a move reports the new date rather
# than citing a stale one.
timeline = [
    (notices[0][2], noticed[0]),
    (settled_at(0), noticed[1]),
    (settled_at(1), noticed[2]),
    (operative[3], operative[0]),
]
instruments = {record["by"] for record in supersessions}
cutovers = {noticed[index]: settled_at(index) for index in range(len(noticed))}


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
# Eight, not the five the written-notice reading finds: the clerk phoned
# one reset through five days before the notice, and three mentions fall
# in the interval between the report and the paper. One of the three is
# the firm's own stipulation mail, which was drafted against a setting
# that had already been vacated by telephone.
if len(stale) != 8:
    sys.exit(f"expected exactly eight stale citations, found {stale}")
if not reported:
    sys.exit(
        "no reset was reported before it was confirmed; the docketing rule "
        "has nothing to bite on and the audit is a timestamp sort again"
    )
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
