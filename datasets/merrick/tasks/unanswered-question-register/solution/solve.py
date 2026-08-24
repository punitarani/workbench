"""Reference solver: questions no addressee answered within three working days.

The window is 19 calendar days: the first 15 working days, ending
Friday 23 January 2026, which is the boundary the brief states.
Fill it from a measurement of the finished record, never from intuition.

This task exists because the one it replaced died of a defect worth naming.
`double-booked-week` was justified by a true measurement -- 54 genuine diary
clashes against 240 merely-adjacent pairs -- that turned out to be 87% one
day's seeding burst. A rate computed over a window can be dominated by what
happens at a boundary, and a total never shows it.

So this task's numbers were checked by date before anything was written, and
the check found the mirror image at the *other* edge: questions asked on the
last recorded day run 4-for-4 unanswered, and the day before 3-of-5, against
1-2 a day everywhere else -- because the world stopped before anyone could
reply. Here that shapes the rule instead of killing the task. The response
window is fixed at three working days and the register must close at least
three working days before the record does, which is stated in the brief as a
constraint on the boundary rather than left to whoever fills it in.

**Three levers, all measured on the record, none invented:**

*Working days, not days.* Reply lag has a median of six minutes and a 90th
percentile of 77 hours, so a meaningful share of replies land either side of
a three-day line. Counting calendar days moves rows.

*Late replies are still rows.* Four of the thirty unanswered questions were
eventually answered, after the window had run. "Did anybody ever reply" is a
different question and returns a different list.

*Cc is not asked.* Only `To` counts, for the question and for the answer.

The admitted-question test is a single character on purpose. "Detect a
question" needs a model in the loop, and an oracle that needs a model to
adjudicate it has only moved the uncertainty into the answer key.
"""

import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("unanswered.json")

# Calendar days, not working days: the cutoff is `WINDOW_DAYS * 86_400`
# and counts every day, while the brief quotes the working-day figure
# because that is what a reader thinks in. The two differ by every weekend
# inside the window, and the verifier takes this same integer, so filling
# it from the working-day figure would shorten the corpus silently and the
# cross-check could not see it.
#
# 19 calendar days = 15 working days, ending Friday 23 January 2026, which
# is the boundary the brief states. It closes months before the record's
# last day, so every row has had its three working days to be answered in.
WINDOW_DAYS: int = 19

# The response window, in working days. Day zero is the day the question was
# sent, so a Thursday question is still answered in time on the following
# Tuesday.
GRACE_WORKING_DAYS = 3


def deadline(
    sent: datetime.date, working_days: int = GRACE_WORKING_DAYS
) -> datetime.date:
    """The last date a reply still counts, counting weekends out.

    Written as a walk rather than as arithmetic on `weekday()`. The closed
    form is four lines shorter and gets the Friday and Saturday cases wrong
    in opposite directions, which is precisely the mistake this task is
    built to catch a model making.
    """

    counted, day = 0, sent
    while counted < working_days:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:
            counted += 1
    return day


def main() -> None:
    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)

    # Seconds from the world's epoch, not a date string. Comparing a served
    # `time` against an ISO date compiles, runs, and windows on a
    # lexicographic accident.
    cutoff = WINDOW_DAYS * 86_400
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    def on(seconds: int) -> datetime.date:
        return (epoch + datetime.timedelta(seconds=seconds)).date()

    # To only. Cc is copied, not asked, and the same distinction decides
    # whether a later message counts as the answer.
    addressed: dict[str, set[str]] = {}
    for message_id, person_id, kind in gmail.execute(
        "SELECT message_id, person_id, kind FROM recipients"
    ):
        if kind == "to":
            addressed.setdefault(message_id, set()).add(person_id)

    threads: dict[str, list[tuple[int, str, str]]] = {}
    messages: dict[str, tuple[str, str, int, str, str]] = {}
    for message_id, thread_id, sender, when, subject, body in gmail.execute(
        "SELECT message_id, thread_id, sender, time, subject, body FROM messages"
    ):
        threads.setdefault(thread_id, []).append((when, sender, message_id))
        messages[message_id] = (thread_id, sender, when, subject, body or "")
    for turns in threads.values():
        turns.sort()

    rows = []
    questions_read = 0
    for message_id, (thread_id, sender, when, subject, body) in messages.items():
        if when >= cutoff:
            continue
        to = addressed.get(message_id)
        if "?" not in body or not to:
            continue
        questions_read += 1
        due = deadline(on(when))
        answered = any(
            later_sender in to and later_when > when and on(later_when) <= due
            for later_when, later_sender, _ in threads[thread_id]
        )
        if answered:
            continue
        rows.append(
            {
                "message_ref": message_id,
                "thread_ref": thread_id,
                "asker": people.get(sender, sender),
                "asked_date": on(when).isoformat(),
                "subject": subject,
                "addressees": sorted(people.get(p, p) for p in to),
            }
        )

    rows.sort(key=lambda r: r["message_ref"])
    OUT.write_text(
        json.dumps(
            {
                "window_end": (epoch + datetime.timedelta(seconds=cutoff - 1))
                .date()
                .isoformat(),
                "questions_read": questions_read,
                "unanswered": rows,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
