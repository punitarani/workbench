#!/bin/sh
# Reference solution: walks the agreement's full version history and finds
# the first version where the licensor indemnity is absent after having
# been present. The change comments are uniformly innocuous and a decoy
# Lumen document sits beside the agreement, so only the content diff
# answers. Fails rather than answer from assumptions.
exec python3 - << 'EOF'
import json
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)
CLAUSE = "Indemnification by Licensor"

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

history = rows(
    "imanage.db",
    "SELECT d.path, v.version, v.author, v.content, v.comment, v.time "
    "FROM versions v JOIN documents d ON d.document_id = v.document_id "
    "WHERE d.path LIKE '%license-and-support-agreement%' ORDER BY v.version",
)
if len(history) < 7:
    sys.exit(f"expected a long version history, found {len(history)} versions")

# The decoy: a similarly named Lumen document that never carried the
# clause. Confirm it is not the one being diffed.
decoy = rows(
    "imanage.db",
    "SELECT v.content FROM versions v JOIN documents d "
    "ON d.document_id = v.document_id WHERE d.path LIKE '%lumen%' "
    "AND d.path NOT LIKE '%license-and-support-agreement%'",
)
if not decoy:
    sys.exit("the similarly named Lumen document is missing from the record")
if any(CLAUSE in content for (content,) in decoy):
    sys.exit("the decoy document unexpectedly carries the clause")

dropped = None
for previous, current in zip(history, history[1:]):
    if CLAUSE in previous[3] and CLAUSE not in current[3]:
        dropped = current
        break
if dropped is None:
    sys.exit(f"no version silently drops {CLAUSE!r}")
path, version, author_id, content, comment, time = dropped
if any(CLAUSE in later[3] for later in history if later[1] > version):
    sys.exit("the clause reappears later; the drop is not silent")
if "indemn" in comment.lower():
    sys.exit("the drop is announced in its comment; nothing silent to find")

# The email record still quotes the old clause AFTER the drop — the wrong
# anchor must exist, and must not fool the version diff.
quotes = rows(
    "gmail.db",
    "SELECT time FROM messages WHERE body LIKE ? ORDER BY time",
    f"%{CLAUSE}%",
)
if not quotes or all(quote_time <= time for (quote_time,) in quotes):
    sys.exit("expected the old clause text quoted in email after the drop")

author = dict(
    rows("imanage.db", "SELECT person_id, name FROM people WHERE person_id = ?",
         author_id)
)[author_id]

clause = {
    "document_path": path,
    "dropped_clause": (
        "Section 9.2 Indemnification by Licensor — Fathom's IP indemnity "
        "covering third-party infringement claims."
    ),
    "dropped_in_version": version,
    "author": author,
    "date": (EPOCH + timedelta(days=time // 86400)).isoformat(),
    "change_comment": comment,
}
with open("clause.json", "w") as handle:
    json.dump(clause, handle, indent=2)
print("clause.json written")
EOF
