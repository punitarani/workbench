#!/bin/sh
# Reference solution: sums the disputed diligence time from Clio activities,
# takes the challenge from the Gmail record, and cross-checks the long Clio
# note. Fails rather than answer from assumptions — the solution must
# retrieve.
exec python3 - << 'EOF'
import json
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
CUTOFF = date(2026, 4, 3)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def day_of(time):
    return EPOCH + timedelta(days=time // 86400)

matter = rows(
    "clio.db",
    "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'",
)
if len(matter) != 1:
    sys.exit(f"expected one Meridian matter, found {len(matter)}")
ticket = matter[0][0]

activities = rows(
    "clio.db",
    "SELECT person, quantity_seconds, time FROM activities "
    "WHERE ticket_id = ? AND (lower(note) LIKE '%diligence%' "
    "OR lower(note) LIKE '%data room%') ORDER BY time",
    ticket,
)
disputed = [
    (person, seconds) for person, seconds, time in activities if day_of(time) > CUTOFF
]
if len(disputed) < 5:
    sys.exit(f"diligence spike after Apr 3 not found: {len(disputed)} entries")
total_minutes = sum(seconds for _, seconds in disputed) // 60
timekeeper_ids = sorted({person for person, _ in disputed})
names = dict(
    rows(
        "clio.db",
        "SELECT person_id, name FROM people WHERE person_id IN (%s)"
        % ",".join("?" * len(timekeeper_ids)),
        *timekeeper_ids,
    )
)

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
if not note or "after April 3" not in note[0][0]:
    sys.exit("the resolution note does not corroborate the Apr 3 cutoff")

dispute = {
    "total_minutes": total_minutes,
    "entry_count": len(disputed),
    "timekeepers": [names[person] for person in timekeeper_ids],
    "challenged_by": challenger,
    "challenge_date": day_of(challenge_time).isoformat(),
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written")
EOF
