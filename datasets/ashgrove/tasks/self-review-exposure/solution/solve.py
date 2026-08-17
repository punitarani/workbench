"""Reference solver: workpapers the file room says were reviewed, and were not.

Self-review is the oldest independence threat there is: the person who
prepared the work signs it off themselves, the file says "reviewed and
approved", and the review never happened. Finding it means refusing to take
the file's word for it.

Two facts per document and they come from opposite directions. Whether
review was *claimed* is in the version comments — prose somebody typed.
Whether review actually *happened* is in the version chain — whether a
second name ever appears on it. iManage serves both on the same call, side
by side, which is exactly what makes believing the wrong one easy.

Ten of this firm's fifty-two workpapers claim a review that their own
authorship contradicts. Not one document has a second author without also
saying so, so the only way to get the count wrong is to trust the comment.
"""

import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("self_review.json")

# The words a version comment uses when it asserts somebody checked the
# work. Stated in the instruction verbatim so the task measures whether an
# agent applies a rule rather than whether it guesses a grader's taste.
CLAIM = re.compile(
    r"review|approv|sign.?off|signed off|checked|second pair|quality control|\bQC\b",
    re.IGNORECASE,
)


def main() -> None:
    imanage = sqlite3.connect(f"file:{STATE / 'imanage.db'}?mode=ro", uri=True)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    names = dict(gmail.execute("SELECT person_id, name FROM people"))

    documents = {
        row[0]: {"document_number": row[1], "document": row[2], "workspace": row[3]}
        for row in imanage.execute(
            "SELECT document_id, document_number, name, workspace FROM documents"
        )
    }
    chain: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    for document_id, version, author, comment in imanage.execute(
        "SELECT document_id, version, author, comment FROM versions "
        "ORDER BY document_id, version"
    ):
        chain[document_id].append((version, author, comment or ""))

    rows = []
    for document_id, document in sorted(
        documents.items(), key=lambda item: item[1]["document_number"]
    ):
        versions = chain.get(document_id, [])
        preparer = versions[0][1] if versions else ""
        # Independent review is a *second name on the chain*, not a claim.
        independent = any(author != preparer for _v, author, _c in versions[1:])
        claimed = any(CLAIM.search(comment) for _v, _a, comment in versions)
        rows.append(
            {
                "document_number": document["document_number"],
                "document": document["document"],
                "preparer": names.get(preparer, preparer),
                "versions": max((v for v, _a, _c in versions), default=0),
                "distinct_authors": len({author for _v, author, _c in versions}),
                "review_claimed": claimed,
                "independently_reviewed": independent,
                # The finding: the file says it was checked and the chain
                # says one pair of hands.
                "self_review_risk": claimed and not independent,
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "documents_total": len(rows),
                "review_claimed_count": sum(r["review_claimed"] for r in rows),
                "independently_reviewed_count": sum(
                    r["independently_reviewed"] for r in rows
                ),
                "self_review_risk_count": sum(r["self_review_risk"] for r in rows),
                "unreviewed_and_unclaimed_count": sum(
                    1
                    for r in rows
                    if not r["review_claimed"] and not r["independently_reviewed"]
                ),
                "at_risk": sorted(
                    r["document_number"] for r in rows if r["self_review_risk"]
                ),
                "documents": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
