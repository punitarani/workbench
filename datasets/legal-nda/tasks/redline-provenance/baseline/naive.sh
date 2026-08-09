#!/bin/sh
# Naive baseline: assumes the redlines live on the inbound draft itself,
# never checking the revision history. Proves the record beats the
# assumption — the surface-obvious answer names the wrong document.
exec python3 - << 'EOF'
import json

provenance = {
    "redline_document_path": "/attachments/inbound-nda-vantage.md",
    "author": "Daniel Reyes",
    "revisions": [2],
    "inbound_draft_revised": True,
}
with open("provenance.json", "w") as handle:
    json.dump(provenance, handle, indent=2)
print("provenance.json written (assumption-only)")
EOF
