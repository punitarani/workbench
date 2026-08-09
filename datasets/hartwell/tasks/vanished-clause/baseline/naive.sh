#!/bin/sh
# Naive baseline: reads only the email trail and assumes the indemnity
# went out with the one revision the emails discuss (the April comments
# round). Proves the version diff discriminates: the actual drop happened
# in a later version whose comment claims formatting cleanup.
exec python3 - << 'EOF'
import json

clause = {
    "document_path": "/lumen-licensing/license-and-support-agreement.md",
    "dropped_clause": (
        "The licensor IP indemnity Fathom objected to in article 9."
    ),
    "dropped_in_version": 2,
    "author": "Marcus Liang",
    "date": "2026-04-21",
    "change_comment": "Incorporated licensee comments on fees and support terms.",
}
with open("clause.json", "w") as handle:
    json.dump(clause, handle, indent=2)
print("clause.json written (email-trail assumption)")
EOF
