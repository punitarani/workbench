"""Reference solver: what each person currently owes, from the firm's mail.

The rule for "is this a promise, and when is it due" is not here. It lives
in `promise_rule`, which `build_tasks` vendors beside this file, and which
`live-commitment-register` reads from too. Two registers over this firm's
prose have to decide that question identically, and a copy per task is the
drift this dataset has already paid for twice.

What IS here is everything about the corpus, because that is what differs:

**Mail, and only mail.** No transcripts, no chat. A promise made in a
meeting is somebody else's register.

**Supersession is per PERSON, not per thread.** That is measured rather
than chosen. Grouping by (sender, thread) puts the share of rows whose date
changes at 2% -- one pair in fifty-nine -- because this firm does not
re-promise inside a thread; it opens a new one. Grouping by sender across
the window puts it at 50%, which is what makes the register worth
computing: over half its rows are dates that moved, and a reader who takes
each person's first promise and stops gets half of them wrong.

That difference is also why this is not the meetings register with a
different table underneath. There, a standing meeting recurs and the same
person revisits the same commitment inside it. Here the recurring context
is the person.

**The window is sixty-one days**, deliberately longer than the meetings
register's forty-two: 530 messages against 623 turns, and the reader has to
carry each person's state across all of them rather than across one
meeting series.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from promise_rule import (  # noqa: E402
    _epoch,
    commitment_in,
    due_date,
)

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("owed.json")

# Calendar days, not working days. The cutoff is `WINDOW_DAYS * 86_400` and
# counts every day; the brief quotes the working-day figure because that is
# what a reader thinks in, and the verifier takes this same integer, so
# filling it from the working-day figure would shorten the corpus silently
# and the cross-check could not see it.
#
# 61 calendar days = 43 working days, ending Thursday 5 March 2026.
# Measured on the shipped record: 530 messages read for 14 rows, 11
# supersessions, and a guessing floor of 14% -- the commonest single due
# date across the register. Narrower windows lose the supersession that is
# the point: at 31 days the share of rows whose date changed is 9%, under
# the floor this dataset refuses below.
WINDOW_DAYS: int = 61


def main() -> int:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    epoch, zone = _epoch(gmail)
    cutoff = WINDOW_DAYS * 86_400
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    def on(seconds: int) -> dt.date:
        return (epoch + dt.timedelta(seconds=seconds)).astimezone(zone).date()

    # Every dated promise, per person, in the order they were made. Ordered
    # by time and not by message id: ids are assigned on write and a thread
    # that arrives out of order would put a later promise earlier, which is
    # precisely the comparison supersession rests on.
    promised: dict[str, list[tuple]] = collections.defaultdict(list)
    messages_read = 0
    for row in gmail.execute(
        "SELECT message_id, sender, time, subject, body FROM messages ORDER BY time"
    ):
        message_id, sender, when, subject, body = row
        if when >= cutoff:
            continue
        messages_read += 1
        token = commitment_in(body or "")
        if token is None:
            continue
        said = on(when)
        promised[sender].append((said, due_date(said, token), message_id, subject))

    rows = []
    superseded = 0
    for sender, made in promised.items():
        # The last thing they said, and how many distinct dates it replaced.
        # Distinct dates, not statements: a person who repeats the same date
        # has not revised anything, and counting the repetition would make
        # `superseded_count` a tally of talkativeness.
        superseded += len({due for _, due, _, _ in made}) - 1
        said, due, message_id, subject = max(made)
        rows.append(
            {
                "owner": people.get(sender, sender),
                "due": due.isoformat(),
                "message_ref": message_id,
                "said_on": said.isoformat(),
                "subject": subject,
            }
        )

    rows.sort(key=lambda r: (r["owner"], r["due"]))
    OUT.write_text(
        json.dumps(
            {
                "window_end": (epoch + dt.timedelta(seconds=cutoff - 1))
                .astimezone(zone)
                .date()
                .isoformat(),
                "messages_read": messages_read,
                "superseded_count": superseded,
                "owed": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
