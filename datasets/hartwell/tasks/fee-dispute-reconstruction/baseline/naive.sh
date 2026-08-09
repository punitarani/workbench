#!/bin/sh
# Naive baseline: no record states the cutoff in the mail or the matter
# note, so the baseline assumes the billing month is the dispute window,
# sums every April diligence entry (sweeping in the pre-cutoff tranche-1
# work), and answers the challenger from the matter note's company name.
# Proves the Slack-only cutoff and the Gmail join discriminate.
exec python3 - << 'EOF'
import json
import sqlite3

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

ticket = rows(
    "clio.db", "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'"
)[0][0]
# Assumption: the whole month of April is disputed (2026-04-01 is day 30).
april = rows(
    "clio.db",
    "SELECT person, quantity_seconds FROM activities WHERE ticket_id = ? "
    "AND (lower(note) LIKE '%diligence%' OR lower(note) LIKE '%data room%') "
    "AND time / 86400 BETWEEN 30 AND 59",
    ticket,
)
names = dict(rows("clio.db", "SELECT person_id, name FROM people"))
dispute = {
    "cutoff_date": "2026-04-01",
    "total_minutes": sum(seconds for _, seconds in april) // 60,
    "entry_count": len(april),
    "timekeepers": sorted({names[person] for person, _ in april}),
    "challenged_by": "Meridian BioLabs",
    "challenge_date": "2026-05-08",
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written (whole-April assumption)")
EOF
