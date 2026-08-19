"""Reference solver: promises made by mail, and whether anyone came back.

A commitment register says what was promised. This asks the next question,
which is the one a practice actually cares about: did the person who
promised it write again in time?

Three things have to be right, per row, and each depends on the last. Find
the promise, in prose, by seven fixed forms. Resolve what date it meant,
against the day it was written. Then look forward in that same thread for
another message from the same person, on or before that date. A mistake at
any step is a wrong row, and a mistake at the first step is a row that
should not exist at all.

Fifty-eight of the hundred and fourteen promises went unanswered by their
own deadline, so neither verdict is the safe guess.
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
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("follow_through.json")

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")
MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
WORD_DAYS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}
# "by April 15th" is the form `by <Month> <day>`; a bare \b after the
# digits drops every ordinal spelling. That defect certified 17 correct
# rows as model errors on the commitment register before anyone noticed,
# because the check that confirmed them used this same pattern.
PATTERNS = (
    ("weekday", r"\bby (?:this |next |)(monday|tuesday|wednesday|thursday|friday)\b"),
    # The firm writes "by end of week" 24 times and "by end of next week"
    # 10 times; it writes "by the end of the week" once. A rule that
    # required the articles admitted 1 of 35 end-of-week promises and
    # called the other 34 hallucinations -- twice, identically, which is
    # the tell for a task defect rather than a model one.
    #
    # No leading "by", for the same reason the day form does not require
    # one: `end of day` and `close of business` have always matched bare,
    # so `end of week` matching only after "by" was an inconsistency a
    # careful reader would trip on rather than a distinction worth making.
    # All three "end of X" families now behave alike.
    ("week", r"\bend of (?:the |this |next )?week\b|\beow\b"),
    ("month", r"\bend of (?:the |this |next )?month\b|\beom\b"),
    ("date", rf"\bby ({'|'.join(MONTHS)}) (\d{{1,2}})(?:st|nd|rd|th)?\b"),
    ("day", r"\b(?:eod|cob|end of day|close of business)\b"),
    ("within", r"\bwithin (\d+|a|two|three|five|ten) (?:business )?days?\b"),
    ("tomorrow", r"\bby tomorrow\b"),
)


def _due(kind: str, match: re.Match, sent: datetime.date) -> datetime.date:
    if kind == "weekday":
        ahead = (WEEKDAYS.index(match.group(1).lower()) - sent.weekday()) % 7
        return sent + datetime.timedelta(days=ahead or 7)
    if kind == "week":
        return sent + datetime.timedelta(days=(4 - sent.weekday()) % 7)
    if kind == "month":
        first_next = (sent.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
        return first_next - datetime.timedelta(days=1)
    if kind == "date":
        return datetime.date(
            sent.year, MONTHS.index(match.group(1).lower()) + 1, int(match.group(2))
        )
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
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    names = dict(gmail.execute("SELECT person_id, name FROM people"))

    messages = list(
        gmail.execute(
            "SELECT message_id, thread_id, sender, time, body FROM messages "
            "ORDER BY time, message_id"
        )
    )
    threads: dict[str, list] = defaultdict(list)
    for row in messages:
        threads[row[1]].append(row)

    rows: dict[tuple[str, str], dict] = {}
    for message_id, thread_id, sender, when, body in messages:
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        for kind, pattern in PATTERNS:
            for match in re.finditer(pattern, body, re.IGNORECASE):
                due = _due(kind, match, sent)
                # Came back: the same person, in the same thread, after
                # this message, on or before the day promised. The due date
                # itself counts -- "by Thursday" is met on Thursday.
                followed = any(
                    other[2] == sender
                    and other[3] > when
                    and (epoch + datetime.timedelta(seconds=other[3])).date() <= due
                    for other in threads[thread_id]
                )
                rows[(message_id, due.isoformat())] = {
                    "message_id": message_id,
                    "due_date": due.isoformat(),
                    "author": names.get(sender, sender),
                    "sent_date": sent.isoformat(),
                    "followed_up": followed,
                }

    register = [rows[key] for key in sorted(rows)]
    late = [r for r in register if not r["followed_up"]]
    by_author: dict[str, int] = defaultdict(int)
    for row in late:
        by_author[row["author"]] += 1
    OUT.write_text(
        json.dumps(
            {
                "messages_read": len(messages),
                "commitments_total": len(register),
                "followed_up_count": sum(r["followed_up"] for r in register),
                "unanswered_count": len(late),
                # Most unanswered, then the earlier name -- `max` breaks a
                # tie the other way and the instruction says earlier.
                "worst_offender": min(
                    by_author, key=lambda name: (-by_author[name], name)
                )
                if by_author
                else "",
                "commitments": register,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
