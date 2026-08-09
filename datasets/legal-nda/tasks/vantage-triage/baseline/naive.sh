#!/bin/sh
# Naive baseline: answers only from the playbook, never reading the day's
# record. Proves the vendor-standard clauses discriminate.
exec python3 - << 'EOF'
import json

triage = {
    "clauses": {
        "definition": {
            "decision": "negotiate",
            "basis": (
                "Definition covers unmarked information; require the "
                "marked-or-reasonable-person standard per playbook."
            ),
        },
        "term": {
            "decision": "negotiate",
            "basis": (
                "Perpetual term is non-standard; propose the playbook's "
                "three-year confidentiality obligations."
            ),
        },
        "mutuality": {
            "decision": "accept",
            "basis": "The playbook takes no position on one-way NDAs.",
        },
        "non_solicit": {
            "decision": "negotiate",
            "basis": (
                "Hiring restrictions should be escalated to the GC per the "
                "playbook's customer guidance."
            ),
        },
        "injunctive_relief": {
            "decision": "negotiate",
            "basis": (
                "Keep irreparable-harm language but do not waive proof of "
                "damages, per playbook section 6."
            ),
        },
    }
}
with open("triage.json", "w") as handle:
    json.dump(triage, handle, indent=2)
print("triage.json written (playbook-only)")
EOF
