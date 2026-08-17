"""Reference solver: every deadline promised in the body of a message.

The point of this task is that there is nothing to query. A commitment is
not a column, a flag, or a field anybody fills in — it is a sentence, and
the only way to the register is to read all of the mail and resolve what
each sentence meant on the day it was written.

Every rule is stated verbatim in the instruction, so the task measures
whether an agent can apply seven fixed patterns to three hundred bodies
without missing any, not whether it can guess a grader's taste. The
resolution is deliberately mechanical: `by Friday` is the next Friday
strictly after the sent date whether or not the writer said "next", because
the firm's people do not use that word consistently and a rule that tried
to read their intent could not be graded.

One row per message and due date. A message that says `by Friday` twice
promised one thing; a message that says `by Friday` and `EOD` promised two.
"""

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("commitments.json")

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
MONTHS = (
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
)
WORD_DAYS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}
PATTERNS = (
    ("weekday", r"\bby (?:this |next |)(monday|tuesday|wednesday|thursday|friday)\b"),
    ("week", r"\bby the end of (?:the |this |next |)week\b"),
    ("month", r"\bby the end of (?:the |this |next |)month\b"),
    ("date", rf"\bby ({'|'.join(MONTHS)}) (\d{{1,2}})\b"),
    ("day", r"\b(?:eod|cob|end of day|close of business)\b"),
    ("within", r"\bwithin (\d+|a|two|three|five|ten) (?:business )?days?\b"),
    ("tomorrow", r"\bby tomorrow\b"),
)
NONE = "(none)"


def _due(kind: str, match: re.Match, sent: datetime.date) -> datetime.date:
    if kind == "weekday":
        ahead = (WEEKDAYS.index(match.group(1).lower()) - sent.weekday()) % 7
        # Strictly after: a Friday message saying "by Friday" means the next.
        return sent + datetime.timedelta(days=ahead or 7)
    if kind == "week":
        return sent + datetime.timedelta(days=(4 - sent.weekday()) % 7)
    if kind == "month":
        first_next = (sent.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return first_next - datetime.timedelta(days=1)
    if kind == "date":
        return datetime.date(sent.year, MONTHS.index(match.group(1).lower()) + 1,
                             int(match.group(2)))
    if kind == "day":
        return sent
    if kind == "within":
        count = match.group(1).lower()
        return sent + datetime.timedelta(
            days=int(count) if count.isdigit() else WORD_DAYS[count]
        )
    return sent + datetime.timedelta(days=1)


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)

    # The database dates a message in seconds from the world's epoch, which
    # it carries; the tools serve the same instant as an ISO timestamp.
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )

    people = {
        row[0]: {"name": row[1], "domain": row[2].split("@")[-1], "affiliation": row[3]}
        for row in gmail.execute(
            "SELECT person_id, name, email_address, affiliation FROM people"
        )
    }
    # An organisation is matched to a mail domain by its own name with the
    # punctuation taken out: "Shaw & Associates" -> shawassociates.example.
    organisations = {
        "".join(c for c in name.lower() if c.isalnum()): name
        for (name,) in clio.execute("SELECT name FROM organizations")
    }

    parties: dict[str, set[str]] = defaultdict(set)
    for message_id, person in gmail.execute(
        "SELECT message_id, person_id FROM recipients"
    ):
        parties[message_id].add(person)

    rows: dict[tuple[str, str], dict] = {}
    messages = list(
        gmail.execute("SELECT message_id, sender, time, body FROM messages")
    )
    for message_id, sender, when, body in messages:
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        outside = sorted(
            {
                organisations.get(
                    people[person]["domain"].split(".")[0],
                    people[person]["domain"],
                )
                for person in parties[message_id] | {sender}
                if people.get(person, {}).get("affiliation") == "external"
            }
        )
        for kind, pattern in PATTERNS:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                due = _due(kind, match, sent)
                # Keyed on the pair, so a body that promises the same date
                # twice contributes one row and not two.
                rows[(message_id, due.isoformat())] = {
                    "message_id": message_id,
                    "due_date": due.isoformat(),
                    "author": people[sender]["name"],
                    "sent_date": sent.isoformat(),
                    "counterparty": outside[0] if outside else NONE,
                }

    register = [rows[key] for key in sorted(rows)]
    by_due: dict[str, int] = defaultdict(int)
    by_party: dict[str, int] = defaultdict(int)
    for row in register:
        by_due[row["due_date"]] += 1
        by_party[row["counterparty"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": len(messages),
                "commitments_total": len(register),
                "messages_with_commitment": len({r["message_id"] for r in register}),
                # Most, then the earlier date / earlier name -- `min` on a
                # negated count, because `max` breaks a tie the other way and
                # the instruction says earlier.
                "busiest_due_date": min(
                    by_due, key=lambda date: (-by_due[date], date)
                ),
                "top_counterparty": min(
                    by_party, key=lambda name: (-by_party[name], name)
                ),
                "commitments": register,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
