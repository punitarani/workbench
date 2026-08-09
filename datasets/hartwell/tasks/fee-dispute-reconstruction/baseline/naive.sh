#!/bin/sh
# Naive baseline: no record states the cutoff in the mail or the matter
# note, so the baseline assumes the billing month is the dispute window,
# sums every April diligence entry on the matter (sweeping in the
# pre-cutoff tranche-1 work and the cutoff-day entry), and answers the
# challenger from the matter note's company name. Proves the Slack-only
# cutoff and the per-entry Clio join discriminate.
exec python3 - << 'EOF'
import json
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def day_of(time):
    return EPOCH + timedelta(days=time // 86400)

ticket = rows(
    "clio.db", "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'"
)[0][0]
# Assumption: the whole month of April is disputed (2026-04-01 is day 30).
april = [
    (activity_id, person, seconds, time)
    for activity_id, t, person, seconds, note, time in rows(
        "clio.db",
        "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
        "quantity_seconds, note, time FROM activities",
    )
    if t == ticket
    and ("diligence" in note.lower() or "data room" in note.lower())
    and 30 <= time // 86400 <= 59
]
names = dict(rows("clio.db", "SELECT person_id, name FROM people"))
by_keeper = {}
for _, person, seconds, _ in april:
    by_keeper[names[person]] = by_keeper.get(names[person], 0) + seconds // 60
dispute = {
    "cutoff_date": "2026-04-01",
    "total_minutes": sum(seconds for _, _, seconds, _ in april) // 60,
    "entry_count": len(april),
    "entries": [
        {"id": activity_id, "date": day_of(time).isoformat(), "minutes": seconds // 60}
        for activity_id, _, seconds, time in april
    ],
    "minutes_by_timekeeper": by_keeper,
    "timekeepers": sorted({names[person] for _, person, _, _ in april}),
    "challenged_by": "Meridian BioLabs",
    "challenge_date": "2026-05-08",
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written (whole-April assumption)")
EOF
