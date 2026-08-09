#!/bin/sh
# Reference solution: establishes the budget-call cutoff from the one
# record that states it (the billing-channel Slack message), sums the
# disputed diligence time from Clio activities strictly after that date,
# reproduces Clio's positional activity ids for the per-entry listing,
# and takes the challenger from the Gmail record. Fails rather than
# answer from assumptions — the solution must retrieve.
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

def day_of(time):
    return EPOCH + timedelta(days=time // 86400)

# The cutoff date is stated only in the billing channel.
cutoff_posts = rows(
    "slack.db",
    "SELECT m.body FROM messages m JOIN conversations c "
    "ON c.conversation_id = m.conversation_id "
    "WHERE c.name = '#billing' AND m.body LIKE '%Meridian%' "
    "AND lower(m.body) LIKE '%cutoff%'",
)
if len(cutoff_posts) != 1:
    sys.exit(f"expected one billing-channel cutoff post, found {len(cutoff_posts)}")
stated = re.search(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2})\b",
    cutoff_posts[0][0],
)
if stated is None:
    sys.exit("the billing-channel post states no cutoff date")
cutoff = date(2026, MONTHS[stated.group(1).lower()], int(stated.group(2)))

matter = rows(
    "clio.db",
    "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'",
)
if len(matter) != 1:
    sys.exit(f"expected one Meridian matter, found {len(matter)}")
ticket = matter[0][0]

# Positional ids reproduce the Clio server's id space: 1-based position
# in the time-ordered activity list across every matter.
activities = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
    "quantity_seconds, note, time FROM activities",
)

def diligent(note):
    lowered = note.lower()
    return "diligence" in lowered or "data room" in lowered

disputed = [
    (activity_id, person, seconds, time)
    for activity_id, t, person, seconds, note, time in activities
    if t == ticket and diligent(note) and day_of(time) > cutoff
]
decoys = [
    1
    for _, t, _, _, note, time in activities
    if t == ticket and diligent(note) and day_of(time) <= cutoff
]
cutoff_day = [
    1
    for _, t, _, _, note, time in activities
    if t == ticket and diligent(note) and day_of(time) == cutoff
]
cross_matter = [
    1
    for _, t, _, _, note, time in activities
    if t != ticket and diligent(note) and day_of(time) > cutoff
]
if len(disputed) < 5:
    sys.exit(f"diligence spike after the cutoff not found: {len(disputed)} entries")
if len(decoys) < 4 or not cutoff_day:
    sys.exit(
        "expected pre-cutoff diligence decoys including one on the cutoff "
        "day; a naive on-or-after sum would not even be wrong"
    )
if len(cross_matter) < 2:
    sys.exit(
        "expected post-cutoff diligence-worded decoys on other matters; "
        "a keyword-only sum would not even be wrong"
    )

total_minutes = sum(seconds for _, _, seconds, _ in disputed) // 60
timekeeper_ids = sorted({person for _, person, _, _ in disputed})
names = dict(
    rows(
        "clio.db",
        "SELECT person_id, name FROM people WHERE person_id IN (%s)"
        % ",".join("?" * len(timekeeper_ids)),
        *timekeeper_ids,
    )
)
minutes_by_timekeeper = {
    names[person]: sum(s for _, p, s, _ in disputed if p == person) // 60
    for person in timekeeper_ids
}

challenge = rows(
    "gmail.db",
    "SELECT m.sender, m.time FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%April invoice%' "
    "AND p.affiliation = 'external' ORDER BY m.time",
)
if not challenge:
    sys.exit("client challenge email not found in the record")
challenger_id, challenge_time = challenge[0]
challenger = dict(
    rows("gmail.db", "SELECT person_id, name FROM people WHERE person_id = ?",
         challenger_id)
)[challenger_id]

note = rows(
    "clio.db",
    "SELECT detail FROM notes WHERE ticket_id = ? AND length(detail) > 400",
    ticket,
)
if not note or "cap" not in note[0][0].lower():
    sys.exit("the resolution note does not corroborate the capped dispute")
if cutoff.isoformat() in note[0][0] or "April 3" in note[0][0]:
    sys.exit("the note states the cutoff date; the record shape changed")

dispute = {
    "cutoff_date": cutoff.isoformat(),
    "total_minutes": total_minutes,
    "entry_count": len(disputed),
    "entries": [
        {
            "id": activity_id,
            "date": day_of(time).isoformat(),
            "minutes": seconds // 60,
        }
        for activity_id, _, seconds, time in disputed
    ],
    "minutes_by_timekeeper": minutes_by_timekeeper,
    "timekeepers": [names[person] for person in timekeeper_ids],
    "challenged_by": challenger,
    "challenge_date": day_of(challenge_time).isoformat(),
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written")
EOF
