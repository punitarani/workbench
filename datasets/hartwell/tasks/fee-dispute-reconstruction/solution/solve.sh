#!/bin/sh
# Reference solution: establishes the budget-call cutoff from the one
# record that states it (the billing-channel Slack message), sums the
# disputed diligence time from Clio activities strictly after that date,
# reproduces Clio's positional activity ids for the per-entry listing,
# takes the challenger from the Gmail record, and runs the support audit
# as a single anti-join: window entries whose date has no same-day email
# or chat message naming the engagement. Fails rather than answer from
# assumptions — the solution must retrieve.
exec python3 - << 'EOF'
import json
import os
import re
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
MONTHS = {
    name: index + 1
    for index, name in enumerate(
        (
            "january", "february", "march", "april", "may", "june",
            "july", "august", "september", "october", "november", "december",
        )
    )
}

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def day_of(time):
    return EPOCH + timedelta(days=time // 86400)

# The cutoff date is stated only in the billing channel.
cutoff_posts = rows(
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
    cutoff_posts[0][0],
)
if stated is None:
    sys.exit("the billing-channel post states no cutoff date")
cutoff = date(2026, MONTHS[stated.group(1).lower()], int(stated.group(2)))

matter = rows(
    "clio.db",
    "SELECT ticket_id FROM matters WHERE description LIKE '%Meridian%'",
)
if len(matter) != 1:
    sys.exit(f"expected one Meridian matter, found {len(matter)}")
ticket = matter[0][0]

# Positional ids reproduce the Clio server's id space: 1-based position
# in the time-ordered activity list across every matter.
activities = rows(
    "clio.db",
    "SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, ticket_id, person, "
    "quantity_seconds, note, time FROM activities",
)

def diligent(note):
    lowered = note.lower()
    return "diligence" in lowered or "data room" in lowered

disputed = [
    (activity_id, person, seconds, time)
    for activity_id, t, person, seconds, note, time in activities
    if t == ticket and diligent(note) and day_of(time) > cutoff
]
decoys = [
    1
    for _, t, _, _, note, time in activities
    if t == ticket and diligent(note) and day_of(time) <= cutoff
]
cutoff_day = [
    1
    for _, t, _, _, note, time in activities
    if t == ticket and diligent(note) and day_of(time) == cutoff
]
cross_matter = [
    1
    for _, t, _, _, note, time in activities
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
timekeeper_ids = sorted({person for _, person, _, _ in disputed})
names = dict(
    rows(
        "clio.db",
        "SELECT person_id, name FROM people WHERE person_id IN (%s)"
        % ",".join("?" * len(timekeeper_ids)),
        *timekeeper_ids,
    )
)
minutes_by_timekeeper = {
    names[person]: sum(s for _, p, s, _ in disputed if p == person) // 60
    for person in timekeeper_ids
}

challenge = rows(
    "gmail.db",
    "SELECT m.sender, m.time FROM messages m JOIN people p "
    "ON p.person_id = m.sender WHERE m.subject LIKE '%April invoice%' "
    "AND p.affiliation = 'external' ORDER BY m.time",
)
if not challenge:
    sys.exit("client challenge email not found in the record")
challenger_id, challenge_time = challenge[0]
challenger = dict(
    rows("gmail.db", "SELECT person_id, name FROM people WHERE person_id = ?",
         challenger_id)
)[challenger_id]

note = rows(
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
MARKERS = ("meridian", "diagnostics", "00001")
window_end = date(2026, 4, 30)
window = [
    (activity_id, time)
    for activity_id, t, _, _, _, time in activities
    if t == ticket and cutoff < day_of(time) <= window_end
]
if len(window) < 30:
    sys.exit(f"expected a busy disputed window, found {len(window)} entries")

def referenced(text):
    lowered = text.lower()
    return any(marker in lowered for marker in MARKERS)

coverage = {}
for subject, body, time in rows(
    "gmail.db", "SELECT subject, body, time FROM messages"
):
    text = f"{subject} {body}"
    if referenced(text):
        kind = "email-name" if "meridian" in text.lower() else "email-oblique"
        coverage.setdefault(day_of(time), set()).add(kind)
dm_ids = {
    conversation_id
    for (conversation_id,) in rows(
        "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
    )
}
for conversation_id, body, time in rows(
    "slack.db", "SELECT conversation_id, body, time FROM messages"
):
    if referenced(body):
        kind = "chat-dm" if conversation_id in dm_ids else "chat-public"
        coverage.setdefault(day_of(time), set()).add(kind)

unsupported = sorted(
    activity_id for activity_id, time in window if day_of(time) not in coverage
)
if not 4 <= len(unsupported) <= 6:
    sys.exit(f"expected 4-6 unsupported window entries, found {len(unsupported)}")
window_days = {day_of(time) for _, time in window}
if not any(coverage.get(day) == {"chat-dm"} for day in window_days):
    sys.exit("expected a window day supported only through a DM")
if not any(coverage.get(day) == {"email-oblique"} for day in window_days):
    sys.exit("expected a window day supported only by a client-nameless email")

dispute = {
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
    "unsupported_entry_ids": unsupported,
}
with open("dispute.json", "w") as handle:
    json.dump(dispute, handle, indent=2)
print("dispute.json written")
EOF
