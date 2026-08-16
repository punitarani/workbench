"""Reference solver: which work product reached a client, and which did not.

Every rule is one an agent can apply through the tools. Documents are
named the way the repository names them; delivery is decided by whether a
message carrying the document had any recipient outside the firm, which
is exactly what the mail surface serves.

The trap is internal circulation: a workpaper attached to a review thread
among colleagues has been attached to mail and has still not reached
anyone, so it is undelivered — with the fact that it moved internally
recorded rather than lost.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("follow_through.json")


def main() -> None:
    imanage = sqlite3.connect(f"file:{STATE / 'imanage.db'}?mode=ro", uri=True)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)

    documents = {
        row[0]: {"document": row[1], "workspace": row[2]}
        for row in imanage.execute("SELECT document_id, name, workspace FROM documents")
    }
    # Revision one is the author of record: whoever wrote the thing.
    authors = {
        row[0]: row[1]
        for row in imanage.execute(
            "SELECT document_id, author FROM versions WHERE version = 1"
        )
    }
    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    internal = {
        person
        for (person,) in gmail.execute(
            "SELECT person_id FROM people WHERE affiliation = 'internal'"
        )
    }

    recipients: dict[str, set[str]] = {}
    for message_id, person in gmail.execute(
        "SELECT message_id, person_id FROM recipients"
    ):
        recipients.setdefault(message_id, set()).add(person)

    left_the_firm: set[str] = set()
    attached_anywhere: set[str] = set()
    for message_id, document_id in gmail.execute(
        "SELECT message_id, document_id FROM attachments"
    ):
        attached_anywhere.add(document_id)
        if recipients.get(message_id, set()) - internal:
            left_the_firm.add(document_id)

    undelivered = sorted(
        (
            {
                "document": row["document"],
                "author": names.get(authors.get(document_id), ""),
                "workspace": row["workspace"],
                "attached_internally": document_id in attached_anywhere,
            }
            for document_id, row in documents.items()
            if document_id not in left_the_firm
        ),
        key=lambda entry: entry["document"],
    )
    OUT.write_text(
        json.dumps(
            {
                "documents_in_repository": len(documents),
                "delivered_count": len(left_the_firm & set(documents)),
                "internal_only_count": sum(
                    1 for entry in undelivered if entry["attached_internally"]
                ),
                "never_attached_count": sum(
                    1 for entry in undelivered if not entry["attached_internally"]
                ),
                "undelivered": undelivered,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
