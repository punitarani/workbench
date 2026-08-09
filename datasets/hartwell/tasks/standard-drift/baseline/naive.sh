#!/bin/sh
# Naive baseline: answers from the playbook plus the email trail. Diane's
# June 24 email flags the five-year terms, so the term practice is right,
# but keyword search finds nothing on the second clause (the only residuals
# mentions in the mail are the LexiPoint REFUSAL), so the baseline reports
# practice as conforming and cites no redline — and its certification
# covers only the four NDAs the mail ever names, so the survey forfeits.
# Proves the version-content walk over the whole corpus discriminates.
exec python3 - << 'EOF'
import json

drift = {
    "playbook_path": "/firm/playbooks/vendor-nda-playbook.md",
    # The mail trail announces every rider it knows about, so the naive
    # read is that nothing moved silently.
    "silent_versions": [],
    "ndas": {
        "/firm/vendor-ndas/mutual-nda-baymark.md": "conforms",
        "/firm/vendor-ndas/mutual-nda-archway.md": "conforms",
        "/firm/vendor-ndas/mutual-nda-lexipoint.md": "deviates",
        "/firm/vendor-ndas/mutual-nda-ironclad.md": "deviates",
    },
    "term": {
        "playbook_standard": (
            "Confidentiality obligations run three (3) years from "
            "disclosure; longer terms need Managing Partner sign-off."
        ),
        "practice": (
            "Per Diane's June 24 email, the LexiPoint and Ironclad NDAs "
            "both went out with five-year confidentiality terms."
        ),
        "document_path": "/firm/playbooks/vendor-nda-playbook.md",
        "version": 3,
        "date": "2026-03-25",
    },
    "residuals": {
        "playbook_standard": "Reject any residual-knowledge clause outright.",
        "practice": (
            "No deviation found: the only residuals request in the record "
            "(LexiPoint, May 7) was refused, so practice conforms."
        ),
        "document_path": "/firm/playbooks/vendor-nda-playbook.md",
        "version": 3,
        "date": "2026-03-25",
    },
}
with open("drift.json", "w") as handle:
    json.dump(drift, handle, indent=2)
print("drift.json written (playbook-and-mail assumption)")
EOF
