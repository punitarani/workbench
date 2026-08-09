#!/bin/sh
# Naive baseline: anchors on the email trail instead of the version
# record. Keyword search over mail surfaces the one thread where a client
# quoted a protective clause verbatim and outside counsel answered that
# only formatting changed since — so the baseline takes that thread's
# attached document, trusts the claim, and blames the head version.
# Proves the corpus-wide content diff discriminates.
exec python3 - << 'EOF'
import json
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

# The longest block-quoted passage in the mail record is the clause the
# client cared about; its thread names the document via its attachments.
quoted = [
    (max((line for line in body.splitlines() if line.startswith("> ")), key=len),
     thread_id)
    for body, thread_id in rows(
        "gmail.db", "SELECT body, thread_id FROM messages WHERE body LIKE '%> %'"
    )
    if any(line.startswith("> ") for line in body.splitlines())
]
quote, thread_id = max(quoted, key=lambda pair: len(pair[0]))

[(document_id,)] = rows(
    "gmail.db",
    "SELECT a.document_id FROM attachments a JOIN messages m "
    "ON m.message_id = a.message_id WHERE m.thread_id = ? "
    "ORDER BY m.time DESC LIMIT 1",
    thread_id,
)

head = rows(
    "imanage.db",
    "SELECT d.path, v.version, p.name, v.comment, v.time "
    "FROM versions v JOIN documents d ON d.document_id = v.document_id "
    "JOIN people p ON p.person_id = v.author "
    "WHERE d.document_id = ? ORDER BY v.version DESC LIMIT 1",
    document_id,
)[0]
path, version, author, comment, time = head

clause = {
    "document_path": path,
    "dropped_clause": quote.removeprefix("> ")[:160],
    "dropped_in_version": version,
    "author": author,
    "date": (EPOCH + timedelta(days=time // 86400)).isoformat(),
    "change_comment": comment,
}
with open("clause.json", "w") as handle:
    json.dump(clause, handle, indent=2)
print("clause.json written (email-trail head-version assumption)")
EOF
