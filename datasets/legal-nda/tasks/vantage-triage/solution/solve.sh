#!/bin/sh
# Reference solution: reads the day's record from the projected databases,
# verifies the vendor standard is actually there, and writes the memo.
# Fails rather than answer from assumptions — the solution must retrieve.
exec python3 - << 'EOF'
import json
import os
import sqlite3
import sys

STATE = os.environ.get("WORKBENCH_STATE", "../state")


def rows(db, sql, *params):
    with sqlite3.connect(f"file:{STATE}/{db}?mode=ro", uri=True) as connection:
        return connection.execute(sql, params).fetchall()

# Retrieve Daniel's redline of the inbound Vantage draft and his report.
revisions = rows(
    "imanage.db",
    "SELECT content, comment FROM versions WHERE author=? ORDER BY version",
    "per-daniel-reyes",
)
statements = rows(
    "gmail.db",
    "SELECT body FROM messages WHERE sender=? AND (body LIKE '%term cap%' "
    "OR body LIKE '%mutual%')",
    "per-daniel-reyes",
)
record = " ".join(c + " " + s for c, s in revisions).lower()
record += " ".join(b for (b,) in statements).lower()

for needle in ("mutual", "two year"):
    if needle not in record.replace("-", " "):
        sys.exit(f"vendor standard not found in the record: {needle!r}")

playbook = rows(
    "imanage.db",
    "SELECT content FROM versions WHERE document_id="
    "(SELECT document_id FROM documents WHERE path LIKE '%playbook%') "
    "ORDER BY version DESC LIMIT 1",
)[0][0].lower()
assert "reasonable person" in playbook and "damages" in playbook

triage = {
    "clauses": {
        "definition": {
            "decision": "negotiate",
            "basis": (
                "The draft sweeps in all disclosed information whether or not "
                "marked; playbook section 1 requires the marked-or-reasonable "
                "person standard (reasonableness qualifier)."
            ),
        },
        "term": {
            "decision": "negotiate",
            "basis": (
                "Perpetual obligations are out; per Daniel's redline the firm "
                "capped the confidentiality term at two years (two-year term "
                "cap for vendor NDAs)."
            ),
        },
        "mutuality": {
            "decision": "negotiate",
            "basis": (
                "Unilateral vendor draft converted to a mutual NDA per the "
                "commercial team's vendor standard, as applied in today's "
                "redline."
            ),
        },
        "non_solicit": {
            "decision": "reject",
            "basis": (
                "Daniel removed the non-solicit clause outright: it doesn't "
                "belong in an NDA."
            ),
        },
        "injunctive_relief": {
            "decision": "negotiate",
            "basis": (
                "Playbook section 6: keep the irreparable-harm acknowledgment "
                "but never waive the requirement to prove damages or post bond."
            ),
        },
    }
}
with open("triage.json", "w") as handle:
    json.dump(triage, handle, indent=2)
print("triage.json written")
EOF
