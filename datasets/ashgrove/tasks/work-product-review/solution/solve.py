"""Reference solver: what the file room knows about every workpaper.

Three facts per document, and each comes from a different place. Who
wrote it is version one's author. Whether anyone reviewed it is whether
any later version carries a different name — the firm's central control,
visible only in the version chain. Whether it reached a client is whether
any message carrying it had a recipient outside the firm.

Every rule here is one an agent can apply through the tools: iManage
serves a document's versions with an author on each, and the mail surface
serves attachments with their recipients. Nothing is read from a column
the servers keep to themselves.

Delivery is decided by affiliation rather than by address, because the
firm's own people appear in the record with names and ids as well as
addresses, and matching on a domain string would break the moment a
client used a personal one.
"""

import json
import os
import sqlite3
import sys
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("work_product_review.json")


def main() -> None:
    imanage = sqlite3.connect(f"file:{STATE / 'imanage.db'}?mode=ro", uri=True)
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)

    # Identified by iManage's own document number, because a name is not
    # an identity here: three workpapers share one title, one workspace,
    # one author and one path, and are separate documents only by number.
    # A key that cannot tell them apart caps a perfect answer at 49/52 --
    # the same defect a composite (name, workspace) key was introduced to
    # fix, returning in a world that put the duplicates in one workspace.
    documents = {
        row[0]: {"document_number": row[1], "document": row[2], "workspace": row[3]}
        for row in imanage.execute(
            "SELECT document_id, document_number, name, workspace FROM documents"
        )
    }

    # The version chain, in order, so the first author and every later one
    # are both available.
    chain: dict[str, list[tuple[int, str]]] = {}
    for document_id, version, author in imanage.execute(
        "SELECT document_id, version, author FROM versions "
        "ORDER BY document_id, version"
    ):
        chain.setdefault(document_id, []).append((version, author))

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

    attached: set[str] = set()
    external: set[str] = set()
    for message_id, document_id in gmail.execute(
        "SELECT message_id, document_id FROM attachments"
    ):
        attached.add(document_id)
        if recipients.get(message_id, set()) - internal:
            external.add(document_id)

    rows = []
    for document_id, document in sorted(
        documents.items(), key=lambda item: item[1]["document_number"]
    ):
        versions = chain.get(document_id, [])
        first_author = versions[0][1] if versions else ""
        rows.append(
            {
                "document_number": document["document_number"],
                "document": document["document"],
                "workspace": document["workspace"],
                "author": names.get(first_author, ""),
                "versions": max((version for version, _ in versions), default=0),
                "reviewed": any(
                    author != first_author for _version, author in versions[1:]
                ),
                "reached_client": document_id in external,
            }
        )

    OUT.write_text(
        json.dumps(
            {
                "documents_total": len(documents),
                "reviewed_count": sum(1 for row in rows if row["reviewed"]),
                "unreviewed_count": sum(1 for row in rows if not row["reviewed"]),
                "reached_client_count": len(external & set(documents)),
                "never_attached_count": sum(
                    1 for document_id in documents if document_id not in attached
                ),
                "documents": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
