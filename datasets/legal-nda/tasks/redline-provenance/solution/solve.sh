#!/bin/sh
# Reference solution: reads the repository's revision history and answers
# only from the record. Fails rather than answer from assumptions.
exec python3 - << 'EOF'
import json
import sqlite3
import sys

def rows(db, sql, *params):
    with sqlite3.connect(f"file:state/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

# Today's redline edits: post-genesis revisions whose summaries name Vantage.
redlines = rows(
    "dms.db",
    "SELECT r.document_id, d.path, r.revision, r.author FROM revisions r "
    "JOIN documents d ON d.document_id = r.document_id "
    "WHERE r.revision > 1 AND lower(r.change_summary) LIKE '%vantage%' "
    "ORDER BY r.revision",
)
if not redlines:
    sys.exit("no Vantage redline revisions found in the record")
paths = {path for _, path, _, _ in redlines}
authors = {author for _, _, _, author in redlines}
if len(paths) != 1 or len(authors) != 1:
    sys.exit(f"ambiguous redline record: paths={paths} authors={authors}")

inbound = rows(
    "dms.db",
    "SELECT head_revision FROM documents WHERE path LIKE '%inbound-nda-vantage%'",
)
if not inbound:
    sys.exit("inbound Vantage draft not found in the repository")

provenance = {
    "redline_document_path": paths.pop(),
    "author": authors.pop(),
    "revisions": sorted(revision for _, _, revision, _ in redlines),
    "inbound_draft_revised": inbound[0][0] > 1,
}
with open("provenance.json", "w") as handle:
    json.dump(provenance, handle, indent=2)
print("provenance.json written")
EOF
