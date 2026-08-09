#!/bin/sh
# Naive baseline: answers from the playbook alone and assumes practice
# conforms to it. Proves the redline-history citations discriminate.
exec python3 - << 'EOF'
import json

drift = {
    "playbook_path": "/firm/playbooks/vendor-nda-playbook.md",
    "term": {
        "playbook_standard": (
            "Confidentiality obligations run three (3) years from "
            "disclosure; longer terms need Managing Partner sign-off."
        ),
        "practice": (
            "Redlines go out on the playbook's three-year term as a hard rule."
        ),
        "document_path": "/firm/playbooks/vendor-nda-playbook.md",
        "version": 3,
        "date": "2026-03-25",
    },
    "residuals": {
        "playbook_standard": "Reject any residual-knowledge clause outright.",
        "practice": (
            "Residual-knowledge clauses are rejected outright per the playbook."
        ),
        "document_path": "/firm/playbooks/vendor-nda-playbook.md",
        "version": 3,
        "date": "2026-03-25",
    },
}
with open("drift.json", "w") as handle:
    json.dump(drift, handle, indent=2)
print("drift.json written (playbook-only)")
EOF
