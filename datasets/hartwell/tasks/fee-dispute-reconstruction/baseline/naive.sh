#!/bin/sh
# Naive baseline: no record states the cutoff in the mail or the matter
# note, so the baseline assumes the billing month is the dispute window,
# sums every April diligence entry on the matter (sweeping in the
# pre-cutoff tranche-1 work and the cutoff-day entry), and answers the
# challenger from the matter note's company name. For the support audit
# it greps only the client's name over email and public channels — the
# obvious single search — so DM-supported and deal-name-only days come
# out as false orphans. Proves the Slack-only cutoff, the per-entry
# Clio join, and the full-surface reconciliation all discriminate.
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

# Support audit, the obvious way: one client-name grep over email and
# the public channels; DMs and deal-name-only references never checked.
supported = set()
gmail_support = {}
for message_id, time in rows(
    "gmail.db",
    "SELECT message_id, time FROM messages WHERE lower(subject) LIKE '%meridian%' "
    "OR lower(body) LIKE '%meridian%'",
):
    message_day = day_of(time)
    supported.add(message_day)
    gmail_support.setdefault(message_day, []).append(message_id)
slack_support = {}
for ts, time in rows(
    "slack.db",
    "SELECT m.ts, m.time FROM messages m JOIN conversations c "
    "ON c.conversation_id = m.conversation_id WHERE c.kind = 'channel' "
    "AND lower(m.body) LIKE '%meridian%'",
):
    message_day = day_of(time)
    supported.add(message_day)
    slack_support.setdefault(message_day, []).append(ts)
window = sorted(
    (activity_id, time, seconds, rate_cents, billable)
    for activity_id, t, _, seconds, _, time, rate_cents, billable in rows(
        "clio.db",
        "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
        "quantity_seconds, note, time, rate_cents, billable FROM activities",
    )
    if t == ticket and 31 <= time // 86400 <= 59
)
unsupported = [entry for entry in window if day_of(entry[1]) not in supported]
by_day = {}
for entry in unsupported:
    by_day.setdefault(day_of(entry[1]), []).append(entry)

def billed_cents(seconds, rate_cents, billable):
    if rate_cents is None or not billable:
        return 0
    return round(round(rate_cents / 100 * seconds / 3600, 2) * 100)

window_by_day = {}
for entry in window:
    window_by_day.setdefault(day_of(entry[1]), []).append(entry)

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
    "support_audit": [
        {
            "date": day.isoformat(),
            "entry_ids": [activity_id for activity_id, _, _, _, _ in entries],
            "entry_count": len(entries),
            "minutes": sum(seconds for _, _, seconds, _, _ in entries) // 60,
            "billed_cents": sum(
                billed_cents(seconds, rate_cents, billable)
                for _, _, seconds, rate_cents, billable in entries
            ),
            "gmail_message_ids": gmail_support.get(day, []),
            "slack_message_ts": slack_support.get(day, []),
            "supported": day in supported,
        }
        for day, entries in sorted(window_by_day.items())
    ],
    "unsupported_days": [
        {
            "date": day.isoformat(),
            "entry_ids": [activity_id for activity_id, _, _, _, _ in entries],
            "entry_count": len(entries),
            "minutes": sum(seconds for _, _, seconds, _, _ in entries) // 60,
            "billed_cents": sum(
                billed_cents(seconds, rate_cents, billable)
                for _, _, seconds, rate_cents, billable in entries
            ),
        }
        for day, entries in sorted(by_day.items())
    ],
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written (whole-April assumption)")
EOF
