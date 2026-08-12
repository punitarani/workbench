"""Reference oracle for settlement-authority-audit; emits JSON on stdout."""

import json
import os
import re
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


# Each written client instruction, in the order the file states it. The
# effective moment of an instruction is not always the moment its email
# lands:
#   ("self",  None)       -- effective when the email is sent.
#   ("fixed", "<iso>")    -- a stated future effective moment (the board's
#                            authority does not go live until Aug 17).
#   ("trigger", "<subj>") -- a contingent grant that goes live only when a
#                            cross-surface fact occurs; the trigger message
#                            supplies the effective moment and a second
#                            source id.
# (subject, status, amount_cents, amount_rule, economic_basis,
#  required_terms, prohibited_terms, expires_at, effective_kind, effective_arg)
authority_specs = (
    (
        "Marigold — opening demand authority",
        "grant",
        47_500_000,
        "minimum",
        "exclusive",
        [],
        ["confidentiality"],
        "2026-07-17T17:00:00-07:00",
        "self",
        None,
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
        "self",
        None,
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
        "self",
        None,
    ),
    (
        "Marigold — conditional counter authority",
        "grant",
        34_000_000,
        "exact",
        "inclusive",
        ["inventory_transition_60_days"],
        [],
        "2026-08-04T12:00:00-07:00",
        "trigger",
        "Marigold — tolling agreement executed",
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
        "fixed",
        "2026-08-17T09:00:00-07:00",
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
        "self",
        None,
    ),
    (
        "Marigold — supplemental closing authority",
        "grant",
        26_000_000,
        "exact",
        "inclusive",
        ["confidentiality", "mutual_release"],
        ["release_unknown_claims"],
        "2026-09-11T17:00:00-07:00",
        "self",
        None,
    ),
)

mail = {
    subject: (message_id, int(timestamp), body)
    for message_id, subject, timestamp, body in rows(
        "gmail.db",
        "SELECT message_id, subject, time, body FROM messages "
        "WHERE subject LIKE 'Marigold%' ORDER BY time",
    )
}
required_subjects = {subject for subject, *_ in authority_specs}
required_subjects |= {
    arg for *_, kind, arg in authority_specs if kind == "trigger" and arg is not None
}
if not required_subjects <= set(mail):
    sys.exit("the documented client-authority email sequence is incomplete")


def _cents(figure):
    return int(figure.replace(",", "")) * 100


def granted_cents(text):
    """The figure an authority instruction actually authorizes.

    A grant names its number with an operative phrase -- "exactly" or
    "no less than". A bare dollar figure may be the authority being
    withdrawn: "stay at the $390,000 authority" while granting exactly
    $340,000 grants the second number, and reading the first one
    certifies the superseded amount.
    """

    found = re.search(r"(?:exactly|no less than)\s+\$([\d,]+)", text, re.IGNORECASE)
    return None if found is None else _cents(found.group(1))


def offered_cents(text):
    """The figure a proposal puts on the table."""

    found = re.search(r"\$([\d,]+)", text)
    return None if found is None else _cents(found.group(1))


def stated_basis(text):
    lowered = text.lower()
    for phrase, basis in (
        ("inclusive of", "inclusive"),
        ("exclusive of", "exclusive"),
        ("net to", "net_plus_fees"),
        ("all-in", "inclusive"),
    ):
        if phrase in lowered:
            return basis
    return None


# The tables above declare what the file says; the record is what the
# agent reads. Cross-check them, because a table keyed on message
# subjects would otherwise keep certifying an amount the prose no longer
# states -- the answer would drift silently and every test would pass.
for subject, status, amount, *_rest in authority_specs:
    if status != "grant":
        continue
    body = mail[subject][2]
    if granted_cents(body) != amount:
        sys.exit(
            f"{subject!r} grants {granted_cents(body)} in the record but the "
            f"audit claims {amount}"
        )

timeline = []
for (
    subject,
    status,
    amount,
    amount_rule,
    basis,
    required,
    prohibited,
    expires,
    effective_kind,
    effective_arg,
) in authority_specs:
    message_id, timestamp, _body = mail[subject]
    source_pairs = [(timestamp, message_id)]
    if effective_kind == "self":
        effective_at = iso(timestamp)
    elif effective_kind == "fixed":
        effective_at = effective_arg
    else:  # trigger: a contingent grant goes live when the cross-surface
        # fact lands; the trigger message dates it and co-sources it.
        trigger_id, trigger_ts, _trigger_body = mail[effective_arg]
        effective_at = iso(trigger_ts)
        source_pairs.append((trigger_ts, trigger_id))
    timeline.append(
        {
            "effective_at": effective_at,
            "surface": "gmail",
            "source_ids": [ident for _ts, ident in sorted(source_pairs)],
            "status": status,
            "amount_cents": amount,
            "amount_rule": amount_rule,
            "economic_basis": basis,
            "required_terms": sorted(required),
            "prohibited_terms": sorted(prohibited),
            "expires_at": expires,
        }
    )

partner_notes = rows(
    "slack.db",
    "SELECT ts, time, body FROM messages WHERE body LIKE '%Project Marigold%' "
    "AND body LIKE '%Olivia%' ORDER BY time",
)
if len(partner_notes) != 3:
    sys.exit(f"expected three partner-DM authority records, found {len(partner_notes)}")
if granted_cents(partner_notes[0][2]) != 30_000_000:
    sys.exit("the telephoned authority does not state $300,000 in the record")
# The relay, its same-thread clarification, and Olivia's later written
# confirmation all document one authority state (the docketing rule makes it
# operative from the relay, not from the written email that confirms it).
written_confirmation = mail["Marigold — written confirmation of phone authority"]
if granted_cents(written_confirmation[2]) != 30_000_000:
    sys.exit("the written confirmation does not state $300,000 in the record")
grant_sources = [
    (int(partner_notes[0][1]), str(partner_notes[0][0])),
    (int(partner_notes[1][1]), str(partner_notes[1][0])),
    (written_confirmation[1], written_confirmation[0]),
]
grant_source_ids = [ident for _timestamp, ident in sorted(grant_sources)]
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
    "expires_at": "2026-08-13T12:00:00-07:00",
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

# (amount_cents, economic_basis, terms, authority_index, disposition); the
# authority_index points into the chronologically sorted timeline above.
subject_specs = {
    "Marigold proposal 01": (
        50_000_000,
        "exclusive",
        ["mutual_release"],
        0,
        "authorized",
    ),
    "Marigold proposal 02": (
        45_000_000,
        "exclusive",
        ["mutual_release"],
        0,
        "amount_outside_authority",
    ),
    "Marigold proposal 03": (
        49_000_000,
        "exclusive",
        ["confidentiality", "mutual_release"],
        0,
        "nonmonetary_terms_mismatch",
    ),
    "Marigold proposal 04": (
        48_000_000,
        "inclusive",
        ["mutual_release"],
        0,
        "economic_terms_mismatch",
    ),
    "Marigold proposal 05": (
        47_500_000,
        "exclusive",
        ["mutual_release", "no_confidentiality"],
        1,
        "authority_revoked",
    ),
    "Marigold proposal 06": (
        47_500_000,
        "exclusive",
        ["mutual_release"],
        1,
        "authority_revoked",
    ),
    "Marigold proposal 07": (
        39_000_000,
        "exclusive",
        ["mutual_release"],
        2,
        "authorized",
    ),
    "Marigold proposal 08": (
        39_000_000,
        "exclusive",
        ["confidentiality", "mutual_release"],
        2,
        "authorized",
    ),
    "Marigold proposal 09": (
        38_500_000,
        "exclusive",
        ["mutual_release"],
        2,
        "amount_outside_authority",
    ),
    "Marigold proposal 10": (
        39_000_000,
        "exclusive",
        [],
        2,
        "nonmonetary_terms_mismatch",
    ),
    "Marigold proposal 11": (
        39_000_000,
        "inclusive",
        ["mutual_release"],
        2,
        "economic_terms_mismatch",
    ),
    "Marigold proposal 12": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        2,
        "amount_outside_authority",
    ),
    "Marigold proposal 13": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authorized",
    ),
    "Marigold proposal 14": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authorized",
    ),
    "Marigold proposal 15": (
        34_000_000,
        "inclusive",
        ["inventory_transition_60_days"],
        3,
        "authority_expired",
    ),
    "Marigold proposal 16": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        3,
        "authority_expired",
    ),
    "Marigold proposal 17": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        4,
        "authorized",
    ),
    "Marigold proposal 18": (
        30_000_000,
        "inclusive",
        ["general_release"],
        4,
        "nonmonetary_terms_mismatch",
    ),
    "Marigold proposal 19": (
        29_500_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        4,
        "amount_outside_authority",
    ),
    "Marigold proposal 20": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        4,
        "authorized",
    ),
    "Marigold proposal 21": (
        30_000_000,
        "inclusive",
        ["general_release", "payment_within_10_days"],
        5,
        "authority_revoked",
    ),
    "Marigold proposal 22": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        5,
        "authority_revoked",
    ),
    "Marigold proposal 23": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        6,
        "authorized",
    ),
    "Marigold proposal 24": (
        28_500_000,
        "inclusive",
        ["confidentiality"],
        6,
        "economic_terms_mismatch",
    ),
    "Marigold proposal 25": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        6,
        "authorized",
    ),
    "Marigold proposal 26": (
        28_500_000,
        "net_plus_fees",
        ["confidentiality"],
        6,
        "authority_expired",
    ),
    "Marigold proposal 27": (
        27_500_000,
        "inclusive",
        ["mutual_release", "no_confidentiality"],
        7,
        "authorized",
    ),
    "Marigold proposal 28": (
        27_500_000,
        "inclusive",
        ["confidentiality", "mutual_release"],
        7,
        "nonmonetary_terms_mismatch",
    ),
    "Marigold proposal 29": (
        27_500_000,
        "inclusive",
        ["mutual_release", "no_confidentiality"],
        7,
        "authority_expired",
    ),
    "Marigold proposal 30": (
        26_000_000,
        "inclusive",
        ["confidentiality", "mutual_release"],
        8,
        "authorized",
    ),
}

names = dict(rows("gmail.db", "SELECT person_id, name FROM people"))
proposals = rows(
    "gmail.db",
    "SELECT message_id, subject, sender, time, body FROM messages "
    "WHERE subject GLOB 'Marigold proposal [0-9][0-9]' ORDER BY time",
)
if [subject for _, subject, _, _, _ in proposals] != list(subject_specs):
    sys.exit("the outbound Marigold proposal sequence drifted")

proposal_audit = []
for message_id, subject, sender, timestamp, body in proposals:
    amount, basis, terms, authority_index, disposition = subject_specs[subject]
    # Same cross-check as the authority grants: the audited figure has to
    # be the figure the proposal actually put on the table.
    if offered_cents(body) != amount:
        sys.exit(
            f"{subject!r} offers {offered_cents(body)} in the record but the "
            f"audit claims {amount}"
        )
    if stated_basis(body) != basis:
        sys.exit(
            f"{subject!r} is {stated_basis(body)} in the record but the "
            f"audit claims {basis}"
        )
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
