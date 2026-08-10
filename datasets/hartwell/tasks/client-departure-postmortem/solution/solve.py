"""Reference oracle for the client-departure postmortem.

The certified deliverable is emitted on stdout.
"""

import json
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

EPOCH = date(2026, 3, 2)

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()


def iso(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()


# The storyline updates name the client informally; routine chatter cites
# the full matter label. That separation isolates the sentiment arc.
arc = rows(
    "slack.db",
    "SELECT m.chat_message_id, m.body, m.time, m.ts, "
    "(SELECT COUNT(*) FROM reactions r "
    " WHERE r.chat_message_id = m.chat_message_id) "
    "FROM messages m WHERE (m.body LIKE '%Cascadia%' OR m.body LIKE '%Hollis%') "
    "AND m.body NOT LIKE '%Cascadia supplier dispute%' ORDER BY m.time",
)
if len(arc) < 5:
    sys.exit(f"Cascadia sentiment arc not found in Slack: {len(arc)} messages")
happy = arc[0]
if "happy" not in happy[1]:
    sys.exit("the arc does not open with the client reported happy")
negative = next((m for m in arc[1:] if "happy" not in m[1]), None)
if negative is None or negative[4] >= happy[4]:
    sys.exit("no reaction decline from the happy update to the first warning")

milestones = [
    next((m for m in arc if needle in m[1]), None)
    for needle in ("happy", "antsy", "myself", "memo went out", "declined")
]
if any(m is None for m in milestones):
    sys.exit("the five milestone updates of the arc are not all in Slack")
if [m[0] for m in milestones] != [m[0] for m in arc[:5]]:
    sys.exit("the milestone updates are not the first five arc messages in order")
trajectory = [m[4] for m in milestones]
if trajectory != sorted(trajectory, reverse=True):
    sys.exit("the reaction counts do not decline across the arc")

closed = rows(
    "clio.db",
    "SELECT h.time FROM matter_history h JOIN matters t "
    "ON t.ticket_id = h.ticket_id WHERE t.description LIKE '%Cascadia%' "
    "AND h.field = 'status' AND h.new_value = 'closed'",
)
if len(closed) != 1:
    sys.exit(f"expected one Cascadia closure in Clio, found {len(closed)}")

termination = rows(
    "gmail.db",
    "SELECT m.time FROM messages m JOIN people p ON p.person_id = m.sender "
    "WHERE m.subject LIKE '%Cascadia%' AND m.subject LIKE '%termination%' "
    "AND p.affiliation = 'external' ORDER BY m.time",
)
if not termination:
    sys.exit("the client's termination email is not in the record")

# Unanswered client emails: thread anti-join over the client-side
# Cascadia correspondence — answered means a firm-side message later in
# the SAME thread.
internal = {
    person
    for (person,) in rows(
        "gmail.db", "SELECT person_id FROM people WHERE affiliation = 'internal'"
    )
}
mail = rows(
    "gmail.db",
    "SELECT message_id, thread_id, sender, subject, time FROM messages ORDER BY time",
)
client_mail = [
    (message_id, thread_id, time)
    for message_id, thread_id, sender, subject, time in mail
    if sender not in internal and "Cascadia" in subject
]
if len(client_mail) < 9:
    sys.exit(f"expected a real client correspondence fabric, found {len(client_mail)}")
unanswered = sorted(
    message_id
    for message_id, thread_id, time in client_mail
    if not any(
        other_thread == thread_id and other_time > time and other_sender in internal
        for _, other_thread, other_sender, _, other_time in mail
    )
)
if len(unanswered) != 4:
    sys.exit(f"expected exactly four unanswered client emails, found {unanswered}")

letter = rows(
    "imanage.db",
    "SELECT workspace, path FROM documents WHERE path LIKE '%disengagement%'",
)
if len(letter) != 1:
    sys.exit(f"expected one disengagement letter, found {len(letter)}")
workspace, path = letter[0]
on_disk = Path(workspace) / path.rsplit("/", 1)[-1]
if not on_disk.exists():
    sys.exit(f"disengagement letter missing from the matter folder: {on_disk}")

postmortem = {
    "first_negative_signal_date": iso(negative[2]),
    "first_negative_signal_ts": negative[3],
    "happy_update_ts": happy[3],
    "happy_update_reactions": happy[4],
    "first_negative_signal_reactions": negative[4],
    "reaction_trajectory": trajectory,
    "matter_closed_date": iso(closed[0][0]),
    "termination_email_date": iso(termination[0][0]),
    "disengagement_letter_path": path,
    "unanswered_client_emails": unanswered,
}
json.dump(postmortem, sys.stdout, indent=2)
sys.stdout.write("\n")
