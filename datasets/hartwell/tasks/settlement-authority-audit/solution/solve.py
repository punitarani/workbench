"""Reference oracle for settlement-authority-audit; emits JSON on stdout.

Nothing here is a table of answers. Every authority attribute (amount, rule,
economic basis, required and prohibited terms, expiry instant, contingency)
is PARSED from the prose the record actually carries; the operative-authority
timeline is built by honoring the first-reliable-report docketing rule, the
stated-future effect, and the cross-surface condition; and each proposal's
disposition is then COMPUTED by applying the four checks, in priority order,
against the authority operative at the proposal's send instant. The only
declared facts are which message subjects form the documented authority
sequence -- what a professional reads off the file -- and the person ids of
the cast; the dispositions fall out of the rules.
"""

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

# The documented client-authority email sequence, in the order the file states
# it. These are the seven written Olivia instructions the brief points to; the
# $300,000 telephone grant and its revocation live only in the partner DM and
# are discovered from Slack.
AUTHORITY_SUBJECTS = (
    "Marigold — opening demand authority",
    "Marigold — put negotiations on hold",
    "Marigold — revised authority",
    "Marigold — conditional counter authority",
    "Marigold — board authority",
    "Marigold — final authority window",
    "Marigold — supplemental closing authority",
)
TOLLING_SUBJECT = "Marigold — tolling agreement executed"
PHONE_CONFIRMATION_SUBJECT = "Marigold — written confirmation of phone authority"

MONTHS = {
    name: index
    for index, name in enumerate(
        [
            "",
            "January",
            "February",
            "March",
            "April",
            "May",
            "June",
            "July",
            "August",
            "September",
            "October",
            "November",
            "December",
        ]
    )
}


def rows(database: str, query: str, *parameters: object) -> list[tuple]:
    path = f"file:{STATE}/{database}?mode=ro"
    with sqlite3.connect(path, uri=True) as connection:
        return connection.execute(query, parameters).fetchall()


def moment(relative_seconds: float) -> datetime:
    """The Pacific instant of a record at ``relative_seconds`` past the epoch."""
    return EPOCH + timedelta(seconds=int(relative_seconds))


# --- Prose parsers. Each reads one fact off the text the record carries. -----
def _cents(figure: str) -> int:
    return int(figure.replace(",", "")) * 100


def granted(text: str) -> tuple[int | None, str | None]:
    """(amount_cents, rule) an authority statement grants, or (None, None).

    The number is the one carried by an operative phrase -- ``exactly`` (an
    exact grant) or ``no less than`` (a floor). A bare dollar figure is never
    a grant: it may be the authority being withdrawn ("stay at the $390,000
    authority", "put the $300,000 authority on hold")."""
    found = re.search(r"(exactly|no less than)\s+\$([\d,]+)", text, re.IGNORECASE)
    if found is None:
        return None, None
    rule = "minimum" if found.group(1).lower() == "no less than" else "exact"
    return _cents(found.group(2)), rule


def offered(text: str) -> int | None:
    """The figure a proposal puts on the table."""
    found = re.search(r"\$([\d,]+)", text)
    return None if found is None else _cents(found.group(1))


def basis_of(text: str) -> str | None:
    lowered = text.lower()
    if "net to goldleaf" in lowered:
        return "net_plus_fees"
    if "inclusive of" in lowered or "all-in" in lowered:
        return "inclusive"
    if "exclusive of" in lowered:
        return "exclusive"
    return None


def _clock(token: str) -> tuple[int, int]:
    token = token.strip().lower()
    if token == "noon":
        return 12, 0
    match = re.match(r"(\d{1,2}):(\d{2})\s*([ap])\.m\.", token)
    hour, minute, meridiem = int(match.group(1)), int(match.group(2)), match.group(3)
    if meridiem == "p" and hour != 12:
        hour += 12
    if meridiem == "a" and hour == 12:
        hour = 0
    return hour, minute


def _instant(clock_token: str, date_token: str) -> datetime:
    hour, minute = _clock(clock_token)
    name, day = date_token.split()
    return datetime(2026, MONTHS[name], int(day), hour, minute, tzinfo=PACIFIC)


def expiry_of(text: str) -> datetime | None:
    found = re.search(
        r"expires at (noon|\d{1,2}:\d{2}\s*[ap]\.m\.) Pacific on "
        r"([A-Z][a-z]+ \d{1,2})",
        text,
    )
    return None if found is None else _instant(found.group(1), found.group(2))


def fixed_effect_of(text: str) -> datetime | None:
    """A stated future effective instant ("takes effect at ... — not before")."""
    found = re.search(
        r"takes effect at (noon|\d{1,2}:\d{2}\s*[ap]\.m\.) Pacific on "
        r"(?:[A-Z][a-z]+, )?([A-Z][a-z]+ \d{1,2}) ?[-—]+ ?not before",
        text,
    )
    return None if found is None else _instant(found.group(1), found.group(2))


def is_hold(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered for marker in ("on hold", "stand down", "do not send another")
    )


def is_conditional(text: str) -> bool:
    return "does not go live until" in text.lower()


def authority_terms(text: str) -> tuple[list[str], list[str]]:
    """(required, prohibited) normalized terms an authority statement sets."""
    lowered = text.lower()
    required: set[str] = set()
    prohibited: set[str] = set()
    if "do not offer confidentiality" in lowered:
        prohibited.add("confidentiality")
    if "do not offer any release of unknown claims" in lowered:
        prohibited.add("release_unknown_claims")
    if "mutual release" in lowered:
        required.add("mutual_release")
    if "general release" in lowered:
        required.add("general_release")
    if "60-day inventory transition" in lowered:
        required.add("inventory_transition_60_days")
    if "payment within ten calendar days" in lowered:
        required.add("payment_within_10_days")
    if "non-disparagement" in lowered:
        required.add("mutual_non_disparagement")
    if "no confidentiality clause" in lowered:
        required.add("no_confidentiality")
    elif "confidentiality is required" in lowered:
        required.add("confidentiality")
    return sorted(required), sorted(prohibited)


def offered_terms(text: str) -> set[str]:
    """The normalized terms a proposal puts on the table."""
    lowered = text.lower()
    terms: set[str] = set()
    if "mutual release" in lowered:
        terms.add("mutual_release")
    if "general release" in lowered:
        terms.add("general_release")
    if "release of unknown claims" in lowered:
        terms.add("release_unknown_claims")
    if "60-day inventory transition" in lowered:
        terms.add("inventory_transition_60_days")
    if "payment within ten calendar days" in lowered:
        terms.add("payment_within_10_days")
    if "non-disparagement" in lowered:
        terms.add("mutual_non_disparagement")
    if "no confidentiality" in lowered:
        terms.add("no_confidentiality")
    elif "confidentiality" in lowered:
        terms.add("confidentiality")
    return terms


# --- Load the record. --------------------------------------------------------
names = dict(rows("gmail.db", "SELECT person_id, name FROM people"))
mail = {
    subject: (message_id, int(timestamp), body)
    for message_id, subject, timestamp, body in rows(
        "gmail.db",
        "SELECT message_id, subject, time, body FROM messages "
        "WHERE subject LIKE 'Marigold%' ORDER BY time",
    )
}
required_subjects = set(AUTHORITY_SUBJECTS) | {
    TOLLING_SUBJECT,
    PHONE_CONFIRMATION_SUBJECT,
}
if not required_subjects <= set(mail):
    sys.exit("the documented client-authority record is incomplete")

# The partner DM: every relayed client instruction ("Project Marigold" +
# "Olivia"). A grant relay carries an operative amount; a hold relay carries a
# hold instruction and none.
partner_relays = [
    (int(timestamp), str(ts), body)
    for ts, timestamp, body in rows(
        "slack.db",
        "SELECT ts, time, body FROM messages "
        "WHERE body LIKE '%Project Marigold%' AND body LIKE '%Olivia%' "
        "ORDER BY time",
    )
]
grant_relays = [
    (relative, ts, body, granted(body)[0])
    for relative, ts, body in partner_relays
    if not is_hold(body) and granted(body)[0] is not None
]
hold_relays = [
    (relative, ts, body) for relative, ts, body in partner_relays if is_hold(body)
]

tolling_id, tolling_relative, _tolling_body = mail[TOLLING_SUBJECT]
confirm_id, confirm_relative, confirm_body = mail[PHONE_CONFIRMATION_SUBJECT]


def _chrono(pairs: list[tuple[int, str]]) -> list[str]:
    return [token for _relative, token in sorted(pairs)]


# --- Build the operative-authority timeline by parsing each instruction. -----
timeline: list[dict[str, object]] = []
used_grant_relays: set[str] = set()
used_hold_relays: set[str] = set()

for subject in AUTHORITY_SUBJECTS:
    message_id, message_relative, body = mail[subject]
    if is_hold(body):
        # Reported-before-effective hold: the partner relays the stand-down
        # before Olivia's written confirmation. Operative from the relay.
        candidates = [
            (relative, ts)
            for relative, ts, _b in hold_relays
            if relative < message_relative
        ]
        relay_relative, relay_ts = max(candidates)
        used_hold_relays.add(relay_ts)
        effective = moment(min(relay_relative, message_relative))
        sources = _chrono([(relay_relative, relay_ts), (message_relative, message_id)])
        timeline.append(
            {
                "effective_at": effective.isoformat(),
                "_effective": effective,
                "_announced": effective,
                "surface": "slack",
                "source_ids": sources,
                "status": "hold",
                "amount_cents": 0,
                "amount_rule": "none",
                "economic_basis": "none",
                "required_terms": [],
                "prohibited_terms": [],
                "expires_at": "",
                "_expiry": None,
                "_condition": None,
            }
        )
        continue

    amount, rule = granted(body)
    if amount is None:
        sys.exit(f"{subject!r} states no operative grant amount in the record")
    basis = basis_of(body)
    required, prohibited = authority_terms(body)
    expiry = expiry_of(body)
    fixed = fixed_effect_of(body)
    condition = moment(tolling_relative) if is_conditional(body) else None
    sources_pairs = [(message_relative, message_id)]

    if fixed is not None:
        # Stated future effect: known when the email lands, operative later.
        effective, announced = fixed, moment(message_relative)
        surface = "gmail"
    else:
        matched = [
            (relative, ts, relay_body)
            for relative, ts, relay_body, relay_amount in grant_relays
            if relay_amount == amount and relative < message_relative
        ]
        if matched:
            # Reported-before-effective: operative from the partner relay.
            relay_relative, relay_ts, relay_body = min(matched)
            if basis_of(relay_body) != basis:
                sys.exit(f"{subject!r} relay and email disagree on economic basis")
            used_grant_relays.add(relay_ts)
            effective = announced = moment(relay_relative)
            surface = "slack"
            sources_pairs.append((relay_relative, relay_ts))
        else:
            effective = announced = moment(message_relative)
            surface = "gmail"

    if condition is not None:
        sources_pairs.append((tolling_relative, tolling_id))
    timeline.append(
        {
            "effective_at": effective.isoformat(),
            "_effective": effective,
            "_announced": announced,
            "surface": surface,
            "source_ids": _chrono(sources_pairs),
            "status": "grant",
            "amount_cents": amount,
            "amount_rule": rule,
            "economic_basis": basis,
            "required_terms": required,
            "prohibited_terms": prohibited,
            "expires_at": expiry.isoformat() if expiry else "",
            "_expiry": expiry,
            "_condition": condition,
        }
    )

# The $300,000 telephone grant: the one grant relay that matches no written
# Olivia authority. Olivia's later written confirmation co-sources it.
orphan_grants = [
    (relative, ts, body, amount)
    for relative, ts, body, amount in grant_relays
    if ts not in used_grant_relays
]
if len(orphan_grants) != 1:
    sys.exit(f"expected exactly one telephone grant relay, found {len(orphan_grants)}")
phone_relative, phone_ts, phone_body, phone_amount = orphan_grants[0]
if granted(confirm_body)[0] != phone_amount:
    sys.exit("the written confirmation and phone relay disagree on the amount")
if basis_of(confirm_body) != basis_of(phone_body):
    sys.exit("the written confirmation and phone relay disagree on economic basis")
phone_required, phone_prohibited = authority_terms(phone_body)
phone_effective = moment(phone_relative)
timeline.append(
    {
        "effective_at": phone_effective.isoformat(),
        "_effective": phone_effective,
        "_announced": phone_effective,
        "surface": "slack",
        "source_ids": _chrono(
            [(phone_relative, phone_ts), (confirm_relative, confirm_id)]
        ),
        "status": "grant",
        "amount_cents": phone_amount,
        "amount_rule": granted(phone_body)[1],
        "economic_basis": basis_of(phone_body),
        "required_terms": phone_required,
        "prohibited_terms": phone_prohibited,
        "expires_at": expiry_of(phone_body).isoformat(),
        "_expiry": expiry_of(phone_body),
        "_condition": None,
    }
)

# Standalone revocations: any hold relay not paired with a written hold email.
for relay_relative, relay_ts, _body in hold_relays:
    if relay_ts in used_hold_relays:
        continue
    effective = moment(relay_relative)
    timeline.append(
        {
            "effective_at": effective.isoformat(),
            "_effective": effective,
            "_announced": effective,
            "surface": "slack",
            "source_ids": [relay_ts],
            "status": "hold",
            "amount_cents": 0,
            "amount_rule": "none",
            "economic_basis": "none",
            "required_terms": [],
            "prohibited_terms": [],
            "expires_at": "",
            "_expiry": None,
            "_condition": None,
        }
    )

timeline.sort(key=lambda record: record["_effective"])


# --- The disposition engine. -------------------------------------------------
def amount_ok(amount: int, state: dict) -> bool:
    if state["amount_rule"] == "minimum":
        return amount >= state["amount_cents"]
    return amount == state["amount_cents"]


def disposition(instant: datetime, amount: int, basis: str, terms: set[str]):
    known = [state for state in timeline if state["_announced"] <= instant]
    operative = None
    for state in known:
        if state["_effective"] <= instant and (
            operative is None or state["_effective"] >= operative["_effective"]
        ):
            operative = state
    pending_newer = any(
        state["_effective"] > instant
        and (operative is None or state["_effective"] > operative["_effective"])
        for state in known
    )
    if operative is None:
        return "authority_not_yet_effective", operative
    if operative["status"] == "hold":
        return "authority_revoked", operative
    if operative["_expiry"] is not None and instant > operative["_expiry"]:
        return (
            "authority_not_yet_effective" if pending_newer else "authority_expired"
        ), operative
    if operative["_condition"] is not None and instant < operative["_condition"]:
        return "condition_unmet", operative
    if not amount_ok(amount, operative):
        return "amount_outside_authority", operative
    if basis != operative["economic_basis"]:
        return "economic_terms_mismatch", operative
    if set(operative["required_terms"]) - terms or (
        set(operative["prohibited_terms"]) & terms
    ):
        return "nonmonetary_terms_mismatch", operative
    return "authorized", operative


# --- Audit every outbound proposal. ------------------------------------------
proposals = rows(
    "gmail.db",
    "SELECT message_id, subject, sender, time, body FROM messages "
    "WHERE subject GLOB 'Marigold proposal [0-9][0-9]' ORDER BY time",
)
proposal_audit: list[dict[str, object]] = []
for message_id, subject, sender, timestamp, body in proposals:
    amount = offered(body)
    basis = basis_of(body)
    if amount is None or basis is None:
        sys.exit(f"{subject!r} states no concrete monetary proposal in the record")
    terms = offered_terms(body)
    instant = moment(int(timestamp))
    verdict, operative = disposition(instant, amount, basis, terms)
    proposal_audit.append(
        {
            "message_id": message_id,
            "sent_at": instant.isoformat(),
            "sender": names[sender],
            "amount_cents": amount,
            "economic_basis": basis,
            "terms": sorted(terms),
            "authority_source_ids": operative["source_ids"] if operative else [],
            "disposition": verdict,
        }
    )

public_timeline = [
    {key: value for key, value in state.items() if not key.startswith("_")}
    for state in timeline
]
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
    "authority_timeline": public_timeline,
    "proposal_audit": proposal_audit,
}
json.dump(answer, sys.stdout, indent=2)
sys.stdout.write("\n")
