"""Reference solution for the Meridian April invoice dispute.

Establishes the budget-call cutoff from the one record that states it (the
billing-channel Slack message), sums the disputed diligence time from Clio
activities strictly after that date, reproduces Clio's positional activity
ids for the per-entry listing, takes the challenger from the Gmail record,
and runs the support audit as a single anti-join: window entries whose date
has no same-day email or chat message naming the engagement, grouped by day
with the affected minutes and billed amount. Fails rather than answer from
assumptions — the solution must retrieve.

Reads the tool databases directly and writes the JSON document to stdout.
Inside Harbor, the staged oracle wrapper runs this exact root-mounted script
as the environment user while solve.sh remains the agent-owned writer.
Outside a container, the state defaults to the unpacked bundle's ``../state``.
"""

import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

type DatabaseValue = str | int | float | bytes | None
type DatabaseRow = tuple[DatabaseValue, ...]
type Activity = tuple[int, str, str, int, str, int, int | None, int]
type WindowEntry = tuple[int, int, int, int | None, int]

EPOCH = date(2026, 3, 2)
MONTHS: dict[str, int] = {
    name: index + 1
    for index, name in enumerate(
        (
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        )
    )
}

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db: str, sql: str, *params: DatabaseValue) -> list[DatabaseRow]:
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def day_of(time: int) -> date:
    return EPOCH + timedelta(days=time // 86400)


# The cutoff date is stated only in the billing channel.
cutoff_posts: list[DatabaseRow] = rows(
    "slack.db",
    "SELECT m.body FROM messages m JOIN conversations c "
    "ON c.conversation_id = m.conversation_id "
    "WHERE c.name = '#billing' AND m.body LIKE '%Meridian%' "
    "AND lower(m.body) LIKE '%cutoff%'",
)
if len(cutoff_posts) != 1:
    sys.exit(f"expected one billing-channel cutoff post, found {len(cutoff_posts)}")
stated = re.search(
    r"\b(January|February|March|April|May|June|July|August|September|"
    r"October|November|December)\s+(\d{1,2})\b",
    str(cutoff_posts[0][0]),
)
if stated is None:
    sys.exit("the billing-channel post states no cutoff date")
cutoff = date(2026, MONTHS[stated.group(1).lower()], int(stated.group(2)))

matter: list[DatabaseRow] = rows(
    "clio.db",
    "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'",
)
if len(matter) != 1:
    sys.exit(f"expected one Meridian matter, found {len(matter)}")
ticket = str(matter[0][0])

# Positional ids reproduce the Clio server's id space: 1-based position
# in the time-ordered activity list across every matter.
activities: list[Activity] = [
    (
        int(activity_id),
        str(activity_ticket),
        str(person),
        int(seconds),
        str(note),
        int(time),
        None if rate_cents is None else int(rate_cents),
        int(billable),
    )
    for (
        activity_id,
        activity_ticket,
        person,
        seconds,
        note,
        time,
        rate_cents,
        billable,
    ) in rows(
        "clio.db",
        "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
        "quantity_seconds, note, time, rate_cents, billable FROM activities",
    )
]


def diligent(note: str) -> bool:
    lowered = note.lower()
    return "diligence" in lowered or "data room" in lowered


disputed: list[tuple[int, str, int, int]] = [
    (activity_id, person, seconds, time)
    for activity_id, t, person, seconds, note, time, _, _ in activities
    if t == ticket and diligent(note) and day_of(time) > cutoff
]
decoys: list[int] = [
    1
    for _, t, _, _, note, time, _, _ in activities
    if t == ticket and diligent(note) and day_of(time) <= cutoff
]
cutoff_day: list[int] = [
    1
    for _, t, _, _, note, time, _, _ in activities
    if t == ticket and diligent(note) and day_of(time) == cutoff
]
cross_matter: list[int] = [
    1
    for _, t, _, _, note, time, _, _ in activities
    if t != ticket and diligent(note) and day_of(time) > cutoff
]
if len(disputed) < 5:
    sys.exit(f"diligence spike after the cutoff not found: {len(disputed)} entries")
if len(decoys) < 4 or not cutoff_day:
    sys.exit(
        "expected pre-cutoff diligence decoys including one on the cutoff "
        "day; a naive on-or-after sum would not even be wrong"
    )
if len(cross_matter) < 2:
    sys.exit(
        "expected post-cutoff diligence-worded decoys on other matters; "
        "a keyword-only sum would not even be wrong"
    )

total_minutes = sum(seconds for _, _, seconds, _ in disputed) // 60
timekeeper_ids: list[str] = sorted({person for _, person, _, _ in disputed})
names: dict[str, str] = {
    str(person_id): str(name)
    for person_id, name in rows(
        "clio.db",
        f"SELECT person_id, name FROM people WHERE person_id IN "
        f"({','.join('?' * len(timekeeper_ids))})",
        *timekeeper_ids,
    )
}
minutes_by_timekeeper: dict[str, int] = {
    names[person]: sum(s for _, p, s, _ in disputed if p == person) // 60
    for person in timekeeper_ids
}

challenge: list[DatabaseRow] = rows(
    "gmail.db",
    "SELECT m.sender, m.time FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%April invoice%' "
    "AND p.affiliation = 'external' ORDER BY m.time",
)
if not challenge:
    sys.exit("client challenge email not found in the record")
challenger_id, challenge_time = challenge[0]
challenger = {
    str(person_id): str(name)
    for person_id, name in rows(
        "gmail.db",
        "SELECT person_id, name FROM people WHERE person_id = ?",
        challenger_id,
    )
}[str(challenger_id)]
challenge_time = int(challenge_time)

note: list[DatabaseRow] = rows(
    "clio.db",
    "SELECT detail FROM notes WHERE ticket_id = ? AND length(detail) > 400",
    ticket,
)
if not note or "cap" not in note[0][0].lower():
    sys.exit("the resolution note does not corroborate the capped dispute")
if cutoff.isoformat() in note[0][0] or "April 3" in note[0][0]:
    sys.exit("the note states the cutoff date; the record shape changed")

# Support audit: a window entry is supported when a same-day email or
# chat message names the engagement — the client (meridian), the deal
# (diagnostics), or the matter number (00001). One pass per surface.
MARKERS: tuple[str, ...] = ("meridian", "diagnostics", "00001")
window_end = date(2026, 4, 30)
window: list[WindowEntry] = [
    (activity_id, time, seconds, rate_cents, billable)
    for activity_id, t, _, seconds, _, time, rate_cents, billable in activities
    if t == ticket and cutoff < day_of(time) <= window_end
]
if len(window) < 30:
    sys.exit(f"expected a busy disputed window, found {len(window)} entries")


def referenced(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in MARKERS)


coverage: dict[date, set[str]] = {}
gmail_support: dict[date, list[str]] = {}
for message_id, subject, body, time in rows(
    "gmail.db",
    "SELECT message_id, subject, body, time FROM messages ORDER BY time, message_id",
):
    text = f"{subject} {body}"
    if referenced(text):
        kind = "email-name" if "meridian" in text.lower() else "email-oblique"
        message_day = day_of(int(time))
        coverage.setdefault(message_day, set()).add(kind)
        gmail_support.setdefault(message_day, []).append(str(message_id))
dm_ids: set[str] = {
    str(conversation_id)
    for (conversation_id,) in rows(
        "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
    )
}
slack_support: dict[date, list[str]] = {}
for conversation_id, ts, body, time in rows(
    "slack.db",
    "SELECT conversation_id, ts, body, time FROM messages ORDER BY time, ts",
):
    body = str(body)
    if referenced(body):
        kind = "chat-dm" if str(conversation_id) in dm_ids else "chat-public"
        message_day = day_of(int(time))
        coverage.setdefault(message_day, set()).add(kind)
        slack_support.setdefault(message_day, []).append(str(ts))

unsupported: list[WindowEntry] = [
    entry for entry in window if day_of(entry[1]) not in coverage
]
unsupported_by_day: dict[date, list[WindowEntry]] = {}
for entry in unsupported:
    unsupported_by_day.setdefault(day_of(entry[1]), []).append(entry)
if len(unsupported_by_day) != 5 or len(unsupported) != 47:
    sys.exit(
        "expected 47 unsupported window entries across 5 days, found "
        f"{len(unsupported)} across {len(unsupported_by_day)} days"
    )
window_days: set[date] = {day_of(time) for _, time, _, _, _ in window}
if not any(coverage.get(day) == {"chat-dm"} for day in window_days):
    sys.exit("expected a window day supported only through a DM")
if not any(coverage.get(day) == {"email-oblique"} for day in window_days):
    sys.exit("expected a window day supported only by a client-nameless email")


def billed_cents(seconds: int, rate_cents: int | None, billable: int) -> int:
    if rate_cents is None or not billable:
        return 0
    public_total = round(rate_cents / 100 * seconds / 3600, 2)
    return round(public_total * 100)


window_by_day: dict[date, list[WindowEntry]] = {}
for entry in window:
    window_by_day.setdefault(day_of(entry[1]), []).append(entry)

support_audit: list[dict[str, object]] = [
    {
        "date": audit_day.isoformat(),
        "entry_ids": [activity_id for activity_id, _, _, _, _ in entries],
        "entry_count": len(entries),
        "minutes": sum(seconds for _, _, seconds, _, _ in entries) // 60,
        "billed_cents": sum(
            billed_cents(seconds, rate_cents, billable)
            for _, _, seconds, rate_cents, billable in entries
        ),
        "gmail_message_ids": gmail_support.get(audit_day, []),
        "slack_message_ts": slack_support.get(audit_day, []),
        "supported": audit_day in coverage,
    }
    for audit_day, entries in sorted(window_by_day.items())
]

unsupported_days: list[dict[str, object]] = [
    {
        "date": unsupported_day.isoformat(),
        "entry_ids": [activity_id for activity_id, _, _, _, _ in entries],
        "entry_count": len(entries),
        "minutes": sum(seconds for _, _, seconds, _, _ in entries) // 60,
        "billed_cents": sum(
            billed_cents(seconds, rate_cents, billable)
            for _, _, seconds, rate_cents, billable in entries
        ),
    }
    for unsupported_day, entries in sorted(unsupported_by_day.items())
]

dispute: dict[str, object] = {
    "cutoff_date": cutoff.isoformat(),
    "total_minutes": total_minutes,
    "entry_count": len(disputed),
    "entries": [
        {
            "id": activity_id,
            "date": day_of(time).isoformat(),
            "minutes": seconds // 60,
        }
        for activity_id, _, seconds, time in disputed
    ],
    "minutes_by_timekeeper": minutes_by_timekeeper,
    "timekeepers": [names[person] for person in timekeeper_ids],
    "challenged_by": challenger,
    "challenge_date": day_of(challenge_time).isoformat(),
    "support_audit": support_audit,
    "unsupported_days": unsupported_days,
}
json.dump(dispute, sys.stdout, indent=2)
sys.stdout.write("\n")
