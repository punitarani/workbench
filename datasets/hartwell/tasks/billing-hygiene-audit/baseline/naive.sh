#!/bin/sh
# Plausible naive approach: find completely silent billable person-days but do
# not perform the same-matter other-person corroboration join. It retrieves the
# population and communication record correctly, yet overstates the exception.
exec python3 - <<'PY'
import json
import os
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(database, sql):
    with sqlite3.connect(f"file:{STATE}/{database}?mode=ro", uri=True) as connection:
        return connection.execute(sql).fetchall()


def day_of(timestamp):
    return EPOCH + timedelta(days=timestamp // 86_400)


def billed_cents(seconds, rate_cents, billable):
    if rate_cents is None or not billable:
        return 0
    return round(round(rate_cents / 100 * seconds / 3_600, 2) * 100)


sent = {
    (sender, day_of(timestamp))
    for sender, timestamp in rows("gmail.db", "SELECT sender, time FROM messages")
}
sent.update(
    (sender, day_of(timestamp))
    for sender, timestamp in rows("slack.db", "SELECT sender, time FROM messages")
)
activities = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time), ticket_id, person, "
    "quantity_seconds, time, rate_cents, billable FROM activities",
)
billable = [entry for entry in activities if entry[6]]
flagged = [
    entry for entry in billable if (entry[2], day_of(entry[4])) not in sent
]
names = dict(rows("clio.db", "SELECT person_id, name FROM people"))
matters = dict(rows("clio.db", "SELECT ticket_id, display_number FROM matters"))
grouped = {}
for entry in flagged:
    grouped.setdefault((day_of(entry[4]), entry[2]), []).append(entry)

days = []
for (entry_day, person), entries in sorted(grouped.items()):
    days.append(
        {
            "date": entry_day.isoformat(),
            "timekeeper": names[person],
            "entry_ids": [entry[0] for entry in entries],
            "matter_numbers": list(dict.fromkeys(matters[entry[1]] for entry in entries)),
            "minutes": sum(entry[3] for entry in entries) // 60,
            "billed_cents": sum(
                billed_cents(entry[3], entry[5], entry[6]) for entry in entries
            ),
        }
    )

notes = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time), author, time FROM notes",
)
hygiene = {
    "entries_reviewed": len(billable),
    "timekeepers_reviewed": len({entry[2] for entry in billable}),
    "anomalous_timekeeper_days": days,
    "anomalous_entry_count": len(flagged),
    "anomalous_minutes_total": sum(entry[3] for entry in flagged) // 60,
    "anomalous_billed_cents_total": sum(
        billed_cents(entry[3], entry[5], entry[6]) for entry in flagged
    ),
    "phantom_note_ids": sorted(
        note_id
        for note_id, author, timestamp in notes
        if (author, day_of(timestamp)) not in sent
    ),
}
with open("hygiene.json", "w") as handle:
    json.dump(hygiene, handle, indent=2)
print("hygiene.json written (silence-only assumption)")
PY
