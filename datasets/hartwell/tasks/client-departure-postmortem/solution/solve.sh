#!/bin/sh
# Reference solution: reads the sentiment arc from Slack, the closure from
# Clio's status history, the termination from Gmail, and the letter from
# the repository. Fails rather than answer from assumptions — every date
# must come from its own system's record.
exec python3 - << 'EOF'
import json
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path

EPOCH = date(2026, 3, 2)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def iso(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()

# The storyline updates name the client informally; routine chatter cites
# the full matter label. That separation isolates the sentiment arc.
arc = rows(
    "slack.db",
    "SELECT m.chat_message_id, m.body, m.time, "
    "(SELECT COUNT(*) FROM reactions r "
    " WHERE r.chat_message_id = m.chat_message_id) "
    "FROM messages m WHERE (m.body LIKE '%Cascadia%' OR m.body LIKE '%Hollis%') "
    "AND m.body NOT LIKE '%Cascadia supplier dispute%' ORDER BY m.time",
)
if len(arc) < 3:
    sys.exit(f"Cascadia sentiment arc not found in Slack: {len(arc)} messages")
happy = arc[0]
if "happy" not in happy[1]:
    sys.exit("the arc does not open with the client reported happy")
negative = next((m for m in arc[1:] if "happy" not in m[1]), None)
if negative is None or negative[3] >= happy[3]:
    sys.exit("no reaction decline from the happy update to the first warning")

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

letter = rows(
    "imanage.db",
    "SELECT workspace, path FROM documents WHERE path LIKE '%disengagement%'",
)
if len(letter) != 1:
    sys.exit(f"expected one disengagement letter, found {len(letter)}")
workspace, path = letter[0]
on_disk = Path("files") / workspace / path.rsplit("/", 1)[-1]
if not on_disk.exists():
    sys.exit(f"disengagement letter missing from the file tree: {on_disk}")

postmortem = {
    "first_negative_signal_date": iso(negative[2]),
    "happy_update_reactions": happy[3],
    "first_negative_signal_reactions": negative[3],
    "matter_closed_date": iso(closed[0][0]),
    "termination_email_date": iso(termination[0][0]),
    "disengagement_letter_path": path,
}
with open("postmortem.json", "w") as handle:
    json.dump(postmortem, handle, indent=2)
print("postmortem.json written")
EOF
