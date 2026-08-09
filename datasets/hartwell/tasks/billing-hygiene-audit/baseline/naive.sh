#!/bin/sh
# Naive baseline: the plausible single-source path. Public surfaces only —
# mail plus the channels chat search actually returns — so every day whose
# only footprint is a direct message reads as silent. The sweep itself is
# real (the counts come out right), which is what makes the rule error, not
# the effort, the thing the grader separates.
exec python3 - << 'EOF'
import json
import os
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()


dm_ids = {
    conversation_id
    for (conversation_id,) in rows(
        "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
    )
}
public = set()
for sender, time in rows("gmail.db", "SELECT sender, time FROM messages"):
    public.add((sender, day_of(time)))
for sender, conversation_id, time in rows(
    "slack.db", "SELECT sender, conversation_id, time FROM messages"
):
    if conversation_id not in dm_ids:
        public.add((sender, day_of(time)))

activities = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, person, quantity_seconds, time "
    "FROM activities",
)
names = dict(rows("clio.db", "SELECT person_id, name FROM people"))
flagged = [
    (activity_id, person, seconds, day_of(time))
    for activity_id, person, seconds, time in activities
    if (person, day_of(time)) not in public
]
notes = rows("clio.db", "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, author, time FROM notes")

hygiene = {
    "entries_reviewed": len(activities),
    "timekeepers_reviewed": len({person for _, person, _, _ in activities}),
    "unsupported_entry_ids": sorted(a for a, _, _, _ in flagged),
    "unsupported_entries": [
        {"id": activity_id, "date": day, "minutes": seconds // 60}
        for activity_id, _, seconds, day in sorted(flagged)
    ],
    "unsupported_minutes_total": sum(s for _, _, s, _ in flagged) // 60,
    "unsupported_timekeepers": sorted({names[person] for _, person, _, _ in flagged}),
    "phantom_note_ids": sorted(
        note_id
        for note_id, author, time in notes
        if (author, day_of(time)) not in public
    ),
}
with open("hygiene.json", "w") as handle:
    json.dump(hygiene, handle, indent=2)
print("hygiene.json written (public-surfaces assumption)")
EOF
