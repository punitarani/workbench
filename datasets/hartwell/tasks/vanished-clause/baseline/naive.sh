#!/bin/sh
# Naive baseline: anchors on the email trail. June quoted the indemnity
# verbatim on June 9 and outside counsel said only formatting changed, so
# the baseline assumes the clause survived until the final pre-signature
# proof and blames the head version. Proves the content diff across the
# long history discriminates.
exec python3 - << 'EOF'
import json
import sqlite3
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

head = rows(
    "imanage.db",
    "SELECT d.path, v.version, p.name, v.comment, v.time "
    "FROM versions v JOIN documents d ON d.document_id = v.document_id "
    "JOIN people p ON p.person_id = v.author "
    "WHERE d.path LIKE '%license-and-support-agreement%' "
    "ORDER BY v.version DESC LIMIT 1",
)[0]
path, version, author, comment, time = head

clause = {
    "document_path": path,
    "dropped_clause": (
        "The licensor IP indemnity in article 9 that Fathom objected to."
    ),
    "dropped_in_version": version,
    "author": author,
    "date": (EPOCH + timedelta(days=time // 86400)).isoformat(),
    "change_comment": comment,
}
with open("clause.json", "w") as handle:
    json.dump(clause, handle, indent=2)
print("clause.json written (email-trail head-version assumption)")
EOF
