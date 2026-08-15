"""Reference solver: which client threads still await the firm.

The rule is mechanical on purpose — stated verbatim in the instruction —
so the task tests whether an agent can apply it to every thread without
missing any, not whether it can guess the grader's taste.
"""

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("open_items.json")

# A client's closing message asks for something when it carries a question
# or one of these request markers. Courtesy acknowledgements do not.
MARKERS = (
    "please send",
    "please provide",
    "please confirm",
    "could you",
    "can you",
    "would you",
    "we need",
    "i need",
    "when will",
    "let me know",
    "waiting on",
    "waiting for",
)


def _asks(body: str) -> bool:
    text = body.lower()
    return "?" in body or any(marker in text for marker in MARKERS)


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    external = {
        row[0]
        for row in gmail.execute(
            "SELECT person_id FROM people WHERE affiliation='external'"
        )
    }
    names = dict(gmail.execute("SELECT person_id, name FROM people"))
    rows = list(
        gmail.execute(
            "SELECT message_id, thread_id, sender, subject, body, time "
            "FROM messages ORDER BY time, message_id"
        )
    )
    threads: dict[str, list] = {}
    for row in rows:
        threads.setdefault(row[1], []).append(row)

    awaiting = []
    for thread_id, messages in threads.items():
        last = messages[-1]
        if last[2] not in external:
            continue
        if not _asks(last[4]):
            continue
        awaiting.append(
            {
                "thread_id": thread_id,
                "message_id": last[0],
                "client": names.get(last[2], last[2]),
                "subject": re.sub(r"^(Re|RE|Fwd):\s*", "", last[3]).strip(),
                "messages_in_thread": len(messages),
            }
        )
    awaiting.sort(key=lambda item: item["thread_id"])

    closed_by_courtesy = sum(
        1
        for messages in threads.values()
        if messages[-1][2] in external and not _asks(messages[-1][4])
    )
    OUT.write_text(
        json.dumps(
            {
                "threads_reviewed": len(threads),
                "awaiting_firm_count": len(awaiting),
                "closed_by_client_courtesy": closed_by_courtesy,
                "awaiting_firm": awaiting,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
