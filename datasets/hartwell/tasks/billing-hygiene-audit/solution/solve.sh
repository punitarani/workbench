#!/bin/sh
# Reference solution: one presence anti-join over every time entry. A
# per-(person, day) sent-message index is built from the full Gmail and
# Slack record — every channel AND every DM — and each of the 1,427
# activities is checked against it; the identical rule flags matter
# notes whose author was silent. Fails rather than answer from
# assumptions — the solution must retrieve, and it asserts the
# single-surface decoys that make a partial sweep wrong.
exec python3 - << 'EOF'
import json
import os
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def day_of(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()

# Per-(person, day) footprint, tagged by surface so the decoy structure
# is verifiable: email, public channel, and DM all count.
dm_ids = {
    conversation_id
    for (conversation_id,) in rows(
        "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
    )
}
footprint = {}
for sender, time in rows("gmail.db", "SELECT sender, time FROM messages"):
    footprint.setdefault((sender, day_of(time)), set()).add("email")
for sender, conversation_id, time in rows(
    "slack.db", "SELECT sender, conversation_id, time FROM messages"
):
    kind = "dm" if conversation_id in dm_ids else "channel"
    footprint.setdefault((sender, day_of(time)), set()).add(kind)

activities = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
    "quantity_seconds, time FROM activities",
)
if len(activities) < 1400:
    sys.exit(f"expected a four-month activity record, found {len(activities)}")
timekeepers = sorted({person for _, _, person, _, _ in activities})

names = dict(rows("clio.db", "SELECT person_id, name FROM people"))

unsupported = [
    (activity_id, person, seconds, day_of(time))
    for activity_id, _, person, seconds, time in activities
    if (person, day_of(time)) not in footprint
]
if not 3 <= len(unsupported) <= 8:
    sys.exit(f"expected 3-8 unsupported entries, found {len(unsupported)}")
if len({person for _, person, _, _ in unsupported}) < 2:
    sys.exit("expected the silent days to span multiple timekeepers")

# The decoys that make single-surface surveys wrong: entry-days whose
# only footprint is a DM (channel search never returns it), or one email.
surface = [
    footprint.get((person, day_of(time)), set())
    for _, _, person, _, time in activities
]
dm_only = sum(1 for kinds in surface if kinds == {"dm"})
email_only = sum(1 for kinds in surface if kinds == {"email"})
if dm_only < 60:
    sys.exit(f"expected heavy DM-only support days, found {dm_only}")
if email_only < 10:
    sys.exit(f"expected email-only support days, found {email_only}")

notes = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, author, time FROM notes",
)
phantom_notes = sorted(
    note_id
    for note_id, author, time in notes
    if (author, day_of(time)) not in footprint
)
if not 2 <= len(phantom_notes) <= 5:
    sys.exit(f"expected a small phantom-note set, found {len(phantom_notes)}")

hygiene = {
    "entries_reviewed": len(activities),
    "timekeepers_reviewed": len(timekeepers),
    "unsupported_entry_ids": sorted(a for a, _, _, _ in unsupported),
    "unsupported_entries": [
        {"id": activity_id, "date": day, "minutes": seconds // 60}
        for activity_id, _, seconds, day in sorted(unsupported)
    ],
    "unsupported_minutes_total": sum(s for _, _, s, _ in unsupported) // 60,
    "unsupported_timekeepers": sorted(
        {names[person] for _, person, _, _ in unsupported}
    ),
    "phantom_note_ids": phantom_notes,
}
with open("hygiene.json", "w") as handle:
    json.dump(hygiene, handle, indent=2)
print("hygiene.json written")
EOF
