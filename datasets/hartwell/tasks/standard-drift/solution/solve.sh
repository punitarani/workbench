#!/bin/sh
# Reference solution: diffs the playbook's standards against the revision
# history of EVERY vendor NDA on file and answers only from the record.
# The residuals flip is invisible to keyword search (no email or chat
# message names the clause for that vendor), so the walk over version
# content is the only path. Fails rather than answer from assumptions.
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
        "WHERE d.path LIKE ? ORDER BY d.path, v.version",
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

# Walk every vendor NDA on file, not just the ones the mail discusses.
nda_paths = sorted(
    {path for path, *_ in versions("%/firm/vendor-ndas/%")}
)
if len(nda_paths) < 4:
    sys.exit(f"expected several vendor NDAs on file, found {len(nda_paths)}")

def first_with(path, needle):
    """First version of ``path`` whose content contains ``needle``."""
    for doc_path, version, author, content, time in versions(path):
        if needle in content:
            return version, time
    return None, None

term_hits = []
residual_hits = []
for path in nda_paths:
    history = versions(path)
    five_version, five_time = first_with(path, "five (5) years")
    if five_version is not None:
        earlier = [c for _, v, _, c, _ in history if v < five_version]
        term_hits.append((path, five_version, five_time, earlier))
    residual_version, residual_time = first_with(path, "Residual Knowledge")
    if residual_version is not None:
        if any(
            "Residual Knowledge" in c for _, v, _, c, _ in history
            if v < residual_version
        ):
            sys.exit(f"{path}: residuals divergence is not a clean boundary")
        residual_hits.append((path, residual_version, residual_time))

conforming = [
    path
    for path in nda_paths
    if path not in {hit[0] for hit in term_hits}
    and path not in {hit[0] for hit in residual_hits}
]
if len(conforming) < 2:
    sys.exit("expected conforming distractor NDAs alongside the divergent ones")

# Term drift: the NDA that started on three years and flipped to five.
flipped = [
    (path, version, time)
    for path, version, time, earlier in term_hits
    if earlier and all("three (3) years" in content for content in earlier)
]
if len(flipped) != 1:
    sys.exit(f"expected exactly one three-to-five term flip, found {len(flipped)}")
lex_path, lex_version, lex_time = flipped[0]

if len(residual_hits) != 1:
    sys.exit(
        f"expected exactly one NDA to gain a residuals clause, "
        f"found {len(residual_hits)}"
    )
iron_path, iron_version, iron_time = residual_hits[0]

# The residuals concession must be keyword-invisible outside the version
# content: no mail or chat names the clause for that vendor.
leaks = rows(
    "gmail.db",
    "SELECT COUNT(*) FROM messages WHERE subject LIKE '%Ironclad%' "
    "AND lower(body) LIKE '%residual%'",
)
chat_leaks = rows(
    "slack.db",
    "SELECT COUNT(*) FROM messages WHERE lower(body) LIKE '%residual%'",
)
if leaks[0][0] or chat_leaks[0][0]:
    sys.exit("the residuals flip leaked into keyword-searchable text")

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
