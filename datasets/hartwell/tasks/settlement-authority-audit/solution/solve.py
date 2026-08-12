"""Reference oracle for settlement-authority-audit; emits JSON on stdout."""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

STATE = os.environ.get("WORKBENCH_STATE", "../state")
PACIFIC = ZoneInfo("America/Los_Angeles")
EPOCH = datetime(2026, 3, 2, tzinfo=PACIFIC)


def rows(database: str, query: str, *parameters: object) -> list[tuple]:
    path = f"file:{STATE}/{database}?mode=ro"
    with sqlite3.connect(path, uri=True) as connection:
        return connection.execute(query, parameters).fetchall()


def iso(relative_seconds: int) -> str:
    return (EPOCH + timedelta(seconds=relative_seconds)).isoformat()


authority_specs = (
    (
        "Marigold — opening demand authority",
        "grant",
        42_500_000,
        "minimum",
        "exclusive",
        [],
        ["confidentiality"],
        "2026-07-17T17:00:00-07:00",
    ),
    (
        "Marigold — put negotiations on hold",
        "hold",
        0,
        "none",
        "none",
        [],
        [],
        "",
    ),
    (
        "Marigold — revised authority",
        "grant",
        39_000_000,
        "exact",
        "exclusive",
        ["mutual_release"],
        [],
        "2026-07-31T17:00:00-07:00",
    ),
    (
        "Marigold — conditional counter authority",
        "grant",
        34_000_000,
        "exact",
        "inclusive",
        ["inventory_transition_60_days"],
        [],
        "2026-08-03T12:00:00-07:00",
    ),
    (
        "Marigold — authority after Monday's call",
        "grant",
        31_500_000,
        "exact",
        "exclusive",
        ["mutual_non_disparagement"],
        ["release_unknown_claims"],
        "2026-08-14T17:00:00-07:00",
    ),
    (
        "Marigold — board authority",
        "grant",
        28_500_000,
        "exact",
        "net_plus_fees",
        ["confidentiality"],
        [],
        "2026-08-28T17:00:00-07:00",
    ),
    (
        "Marigold — final authority window",
        "grant",
        27_500_000,
        "exact",
        "inclusive",
        ["mutual_release", "no_confidentiality"],
        ["confidentiality"],
        "2026-09-04T12:00:00-07:00",
    ),
)

mail = {
    subject: (message_id, int(timestamp))
    for message_id, subject, timestamp in rows(
        "gmail.db",
        "SELECT message_id, subject, time FROM messages "
        "WHERE subject LIKE 'Marigold%' ORDER BY time",
    )
}
if not all(subject in mail for subject, *_ in authority_specs):
    sys.exit("the documented client-authority email sequence is incomplete")

timeline = [
    {
        "effective_at": iso(mail[subject][1]),
        "surface": "gmail",
        "source_ids": [mail[subject][0]],
        "status": status,
        "amount_cents": amount,
        "amount_rule": amount_rule,
        "economic_basis": basis,
        "required_terms": sorted(required),
        "prohibited_terms": sorted(prohibited),
        "expires_at": expires,
    }
    for (
        subject,
        status,
        amount,
        amount_rule,
        basis,
        required,
        prohibited,
        expires,
    ) in authority_specs
]

partner_notes = rows(
    "slack.db",
    "SELECT ts, time, body FROM messages WHERE body LIKE '%Project Marigold%' "
    "AND body LIKE '%Olivia%' ORDER BY time",
)
if len(partner_notes) != 3:
    sys.exit(f"expected three partner-DM authority records, found {len(partner_notes)}")
grant_source_ids = [str(partner_notes[0][0]), str(partner_notes[1][0])]
phone_grant = {
    "effective_at": iso(int(partner_notes[0][1])),
    "surface": "slack",
    "source_ids": grant_source_ids,
    "status": "grant",
    "amount_cents": 30_000_000,
    "amount_rule": "exact",
    "economic_basis": "inclusive",
    "required_terms": ["general_release", "payment_within_10_days"],
    "prohibited_terms": [],
    "expires_at": "2026-08-12T12:00:00-07:00",
}
phone_hold = {
    "effective_at": iso(int(partner_notes[2][1])),
    "surface": "slack",
    "source_ids": [str(partner_notes[2][0])],
    "status": "hold",
    "amount_cents": 0,
    "amount_rule": "none",
    "economic_basis": "none",
    "required_terms": [],
    "prohibited_terms": [],
    "expires_at": "",
}
timeline.extend((phone_grant, phone_hold))
timeline.sort(key=lambda record: record["effective_at"])

subject_specs = {
    "Marigold proposal 01": (
        47_500_000,
        "exclusive",
        ["mutual_release", "no_confidentiality"],
        0,
        "authorized",
    ),
    "Marigold proposal 02": (
        42_000_000,
        "exclusive",
        ["mutual_release", "no_confidentiality"],
        0,
        "amount_outside_authority",
    ),
    "Marigold proposal 03": (
        42_500_000,
        "inclusive",
        ["mutual_release", "no_confidentiality"],
        0,
        "economic_terms_mismatch",
    ),
    "Marigold proposal 04": (
        42_500_000,
        "exclusive",
        ["mutual_release", "no_confidentiality"],
        1,
        "authority_revoked",
    ),
    "Marigold proposal 05": (
        39_000_000,
        "exclusive",
        ["confidentiality", "mutual_release"],
        2,
        "authorized",
    ),
    "Marigold proposal 06": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authorized",
    ),
    "Marigold proposal 07": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authorized",
    ),
    "Marigold proposal 08": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authority_expired",
    ),
    "Marigold proposal 09": (
        31_500_000,
        "exclusive",
        ["mutual_non_disparagement", "release_unknown_claims"],
        4,
        "nonmonetary_terms_mismatch",
    ),
    "Marigold proposal 10": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        5,
        "authorized",
    ),
    "Marigold proposal 11": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        6,
        "authority_revoked",
    ),
    "Marigold proposal 12": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        7,
        "authorized",
    ),
    "Marigold proposal 13": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        7,
        "authorized",
    ),
    "Marigold proposal 14": (
        27_500_000,
        "inclusive",
        ["mutual_release", "no_confidentiality"],
        8,
        "authority_expired",
    ),
}

names = dict(rows("gmail.db", "SELECT person_id, name FROM people"))
proposals = rows(
    "gmail.db",
    "SELECT message_id, subject, sender, time FROM messages "
    "WHERE subject GLOB 'Marigold proposal [0-9][0-9]' ORDER BY time",
)
if [subject for _, subject, _, _ in proposals] != list(subject_specs):
    sys.exit("the outbound Marigold proposal sequence drifted")

proposal_audit = []
for message_id, subject, sender, timestamp in proposals:
    amount, basis, terms, authority_index, disposition = subject_specs[subject]
    proposal_audit.append(
        {
            "message_id": message_id,
            "sent_at": iso(int(timestamp)),
            "sender": names[sender],
            "amount_cents": amount,
            "economic_basis": basis,
            "terms": sorted(terms),
            "authority_source_ids": timeline[authority_index]["source_ids"],
            "disposition": disposition,
        }
    )

breaches = [
    record for record in proposal_audit if record["disposition"] != "authorized"
]
answer = {
    "matter_number": rows(
        "clio.db",
        "SELECT display_number FROM matters WHERE ticket_id='tkt-000010'",
    )[0][0],
    "negotiation_alias": "Project Marigold",
    "client_decision_maker": names["per-olivia-chen"],
    "opposing_counsel": sorted((names["per-derek-strauss"], names["per-mia-denning"])),
    "proposal_count": len(proposal_audit),
    "authorized_count": len(proposal_audit) - len(breaches),
    "breach_count": len(breaches),
    "breach_message_ids": [record["message_id"] for record in breaches],
    "authority_timeline": timeline,
    "proposal_audit": proposal_audit,
}
json.dump(answer, sys.stdout, indent=2)
sys.stdout.write("\n")
