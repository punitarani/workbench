#!/bin/sh
# Naive baseline: trusts only the latest client email and applies its number
# backwards to the entire negotiation, ignoring holds, prior windows, and the
# partner DM that documents telephone authority.
set -eu
exec python3 - <<'PY'
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

state = os.environ.get("WORKBENCH_STATE", "../state")
epoch = datetime(2026, 3, 2, tzinfo=ZoneInfo("America/Los_Angeles"))

def rows(database, query, *parameters):
    with sqlite3.connect(f"file:{state}/{database}?mode=ro", uri=True) as connection:
        return connection.execute(query, parameters).fetchall()

def iso(seconds):
    return (epoch + timedelta(seconds=seconds)).isoformat()

latest = rows(
    "gmail.db",
    "SELECT message_id,time FROM messages WHERE sender='per-olivia-chen' "
    "AND subject LIKE 'Marigold%' ORDER BY time DESC LIMIT 1",
)[0]
messages = rows(
    "gmail.db",
    "SELECT message_id,sender,time,body FROM messages "
    "WHERE subject GLOB 'Marigold proposal [0-9][0-9]' ORDER BY time",
)
names = dict(rows("gmail.db", "SELECT person_id,name FROM people"))
audit = []
for message_id, sender, timestamp, body in messages:
    amount = int(re.search(r"\$([0-9,]+)", body).group(1).replace(",", "")) * 100
    lowered = body.lower()
    basis = (
        "net_plus_fees" if "net to goldleaf" in lowered
        else "inclusive" if "inclusive" in lowered or "all-in" in lowered
        else "exclusive"
    )
    terms = []
    for phrase, label in (
        ("confidentiality", "confidentiality"),
        ("mutual release", "mutual_release"),
        ("general release", "general_release"),
        ("unknown claims", "release_unknown_claims"),
        ("non-disparagement", "mutual_non_disparagement"),
        ("60-day", "inventory_transition_60_days"),
        ("ten calendar days", "payment_within_10_days"),
    ):
        if phrase in lowered:
            terms.append(label)
    if "no confidentiality" in lowered:
        terms = [term for term in terms if term != "confidentiality"]
        terms.append("no_confidentiality")
    audit.append(
        {
            "message_id": message_id,
            "sent_at": iso(timestamp),
            "sender": names[sender],
            "amount_cents": amount,
            "economic_basis": basis,
            "terms": sorted(terms),
            "authority_source_ids": [latest[0]],
            "disposition": (
                "authorized" if amount == 26_000_000 else "amount_outside_authority"
            ),
        }
    )

breaches = [record for record in audit if record["disposition"] != "authorized"]
answer = {
    "matter_number": "00010-GoldleafHospitalityGroup",
    "negotiation_alias": "Project Marigold",
    "client_decision_maker": "Olivia Chen",
    "opposing_counsel": ["Derek Strauss", "Mia Denning"],
    "proposal_count": len(audit),
    "authorized_count": len(audit) - len(breaches),
    "breach_count": len(breaches),
    "breach_message_ids": [record["message_id"] for record in breaches],
    "authority_timeline": [
        {
            "effective_at": iso(latest[1]),
            "surface": "gmail",
            "source_ids": [latest[0]],
            "status": "grant",
            "amount_cents": 26_000_000,
            "amount_rule": "exact",
            "economic_basis": "inclusive",
            "required_terms": ["confidentiality", "mutual_release"],
            "prohibited_terms": ["release_unknown_claims"],
            "expires_at": "2026-09-11T17:00:00-07:00",
        }
    ],
    "proposal_audit": audit,
}
with open("authority.json", "w") as stream:
    json.dump(answer, stream, indent=2)
print("authority.json written (latest-email-only assumption)")
PY
