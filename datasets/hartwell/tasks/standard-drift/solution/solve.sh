#!/bin/sh
# Reference solution: diffs the playbook's standards against the vendor-NDA
# revision history and answers only from the record. Fails rather than
# answer from assumptions — the solution must retrieve.
exec python3 - << 'EOF'
import json
import sqlite3
import sys
from datetime import date, timedelta

EPOCH = date(2026, 3, 2)

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

def iso(time):
    return (EPOCH + timedelta(days=time // 86400)).isoformat()

def versions(path_like):
    found = rows(
        "imanage.db",
        "SELECT d.path, v.version, v.author, v.content, v.time FROM versions v "
        "JOIN documents d ON d.document_id = v.document_id "
        "WHERE d.path LIKE ? ORDER BY v.version",
        path_like,
    )
    if not found:
        sys.exit(f"no document matching {path_like!r} in the repository")
    return found

playbook = versions("%vendor-nda-playbook%")
playbook_path, _, _, playbook_head, _ = playbook[-1]
if "three (3) years" not in playbook_head:
    sys.exit("playbook term standard (three-year cap) not found in the record")
if "Reject any residual-knowledge clause" not in playbook_head:
    sys.exit("playbook residuals standard not found in the record")

def first_divergence(path_like, present, absent_before=None):
    """First version whose content contains ``present``; earlier versions must not."""
    history = versions(path_like)
    for path, version, author, content, time in history:
        if present in content:
            return path, version, author, time
    sys.exit(f"no version of {path_like!r} contains {present!r}")

lex_path, lex_version, _, lex_time = first_divergence(
    "%mutual-nda-lexipoint%", "five (5) years"
)
lex_history = versions("%mutual-nda-lexipoint%")
if any("five (5) years" in content for _, v, _, content, _ in lex_history if v < lex_version):
    sys.exit("LexiPoint divergence is not a clean version boundary")
if not any("three (3) years" in content for _, v, _, content, _ in lex_history if v < lex_version):
    sys.exit("LexiPoint NDA never carried the playbook's three-year term")

iron_path, iron_version, _, iron_time = first_divergence(
    "%mutual-nda-ironclad%", "Residual Knowledge"
)
iron_history = versions("%mutual-nda-ironclad%")
if any(
    "Residual Knowledge" in content
    for _, v, _, content, _ in iron_history
    if v < iron_version
):
    sys.exit("Ironclad divergence is not a clean version boundary")

# The covering emails corroborate that the divergent versions went out.
sent = rows(
    "gmail.db",
    "SELECT COUNT(*) FROM messages m JOIN attachments a "
    "ON a.message_id = m.message_id WHERE a.filename IN (?, ?)",
    "mutual-nda-lexipoint.md",
    "mutual-nda-ironclad.md",
)
if sent[0][0] < 2:
    sys.exit("covering emails for the divergent NDAs not found")

drift = {
    "playbook_path": playbook_path,
    "term": {
        "playbook_standard": (
            "Confidentiality obligations capped at three (3) years; longer "
            "terms need Managing Partner sign-off."
        ),
        "practice": (
            "Agreed to the vendor's five (5) year confidentiality term to "
            "keep the renewal on schedule."
        ),
        "document_path": lex_path,
        "version": lex_version,
        "date": iso(lex_time),
    },
    "residuals": {
        "playbook_standard": (
            "Reject any residual-knowledge clause outright; unaided-memory "
            "information stays confidential."
        ),
        "practice": (
            "Accepted the vendor's position: a Residual Knowledge clause "
            "was added to the signing draft."
        ),
        "document_path": iron_path,
        "version": iron_version,
        "date": iso(iron_time),
    },
}
with open("drift.json", "w") as handle:
    json.dump(drift, handle, indent=2)
print("drift.json written")
EOF
