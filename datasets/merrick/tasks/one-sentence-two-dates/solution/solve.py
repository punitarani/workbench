"""Reference solver: every date the opening days' mail put in writing.

The rule is the same seven date forms the in-band Ashgrove register uses,
and the composition is the part that is new. There, a message was a row.
Here a message is one row *per distinct date it names*, so a sentence
that says the same deadline twice in two forms is one row and a sentence
that says two different deadlines in two forms is two.

That is the mechanism behind the hardest measured date task in this tree:
every trial found the first form in a message and two of nine found the
second. It is not a coverage failure -- the text was read -- it is that a
second date in a sentence already parsed reads as a restatement of the
first, and the rule says it is not.

The row key is `(ref, at)` rather than `ref`, and that is load-bearing
rather than decorative. Two rows out of one message keyed on `ref` alone
collapse to one on both sides of the grader: row F1 still reads 1.000
because both sides dedupe identically, and the ceiling is silently below
1.0 for a reason no agent can fix. `at` is the character position of the
form, so it distinguishes the rows of one message and, separately, it
grades whether the agent located the form or merely recognised that the
message had one in it somewhere.

What the row deliberately does not carry is the *name* of the form that
matched. Printing `end of week` beside the date hands the agent the
checklist the task exists to withhold -- the same decomposition that made
`self-review-exposure` score 1.000 three times over.

measure("once the window is fixed, record here how many of its messages carry two forms resolving to different dates, and how many of those sit in one sentence. Twelve and four are the floors; below them this shape has nothing to measure")

measure("the bound. messages_read counts only the window's messages, never the whole corpus: a figure over everything makes the agent read everything, and on a large record that alone turns a good score into no deliverable at all")
"""
# ruff: noqa: E501
# Long lines are the «MEASURE» questions: written out in full because
# an abbreviated one gets guessed at instead of measured. Truncating
# them once already destroyed what they were for. They go when the
# values land.

import calendar
import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("date_register.json")

# The window, in whole days from the world's own epoch. Left unset on
# purpose: the world is still recording, and a number invented here would
# be a real answer key over an imaginary window. `main` refuses to run
# until it is measured, loudly, rather than writing a plausible oracle.
#
# measure("the number of calendar days in the window. Take the smallest window holding 180-260 messages, measured with datasets/merrick/measure_candidates.py --days N")
#
# The window in full, since the line above no longer carries it: take the
# smallest window whose mail carries >=12 rows and >=12 second-or-later
# rows (`measure_candidates.py --days N` prints both), then write the same
# window into instruction.md as a weekday and a full date. Nothing has to
# be written into tests/verify.py -- it reads that date back out of the
# brief.
#
# Two calendar days is the floor whatever the counts say. A one-day window
# puts the same `sent_date` on every row, and a graded column with one
# value in it grades nothing: an agent that never looks it up and writes
# the majority value scores full marks on it.
WINDOW_DAYS: int | None = None

_WEEKDAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)
_MONTHS = (
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
# `a` and the spelled numbers the instruction lists. measure("which of these spelled numbers the corpus actually writes after 'within'. A word the firm never uses adds a form nothing can match; one it uses and this omits drops real rows")
_NUMBER_WORDS = {"a": 1, "two": 2, "three": 3, "five": 5, "ten": 10}


def _next_weekday(sent: datetime.date, name: str) -> datetime.date:
    """The next such weekday strictly after the sent date."""

    target = _WEEKDAY_NAMES.index(name.capitalize())
    ahead = (target - sent.weekday()) % 7
    return sent + datetime.timedelta(days=ahead or 7)


def _friday_of_week(sent: datetime.date) -> datetime.date:
    """The Friday of the week the message was sent, weeks Monday to Sunday."""

    return sent + datetime.timedelta(days=4 - sent.weekday())


def _end_of_month(sent: datetime.date) -> datetime.date:
    return sent.replace(day=calendar.monthrange(sent.year, sent.month)[1])


def _month_day(match: re.Match, sent: datetime.date) -> datetime.date | None:
    month = _MONTHS.index(match.group(1).lower()) + 1
    try:
        return datetime.date(sent.year, month, int(match.group(2)))
    except ValueError:
        # `by February 30` is not a date and makes no row. Without this the
        # solver raises on one message and the whole build dies rather than
        # the row being absent, which is what the instruction says happens.
        return None


def _within(match: re.Match, sent: datetime.date) -> datetime.date:
    raw = match.group(1).lower()
    days = _NUMBER_WORDS.get(raw, None)
    if days is None:
        days = int(raw)
    return sent + datetime.timedelta(days=days)


# (pattern, which group's start is the position, resolver).
#
# The position group is not always the whole match: the instruction says
# `at` points at the `e` of `end` in "by the end of week", and at the `b`
# of `by` in "by next Tuesday". Group 0 is the whole match; a named group
# is used where the optional words in front are not part of what `at`
# points at.
#
# Every gap inside a form is `\s+`, including the gaps inside `end of
# week` and `close of business`. A literal space there and `\s+` between
# the words in front of it is a rule the brief does not state and the
# verifier does not share: the verifier squashes each run of whitespace
# to one space before it looks, so a body that wraps "end of\nweek" would
# make a row there and none here, and the two would disagree over a
# difference nobody chose.
_FORMS: tuple[tuple[re.Pattern, int, object], ...] = (
    (
        re.compile(
            r"\bby\s+(?:this\s+|next\s+)?"
            r"(monday|tuesday|wednesday|thursday|friday)\b",
            re.IGNORECASE,
        ),
        0,
        lambda m, sent: _next_weekday(sent, m.group(1)),
    ),
    (
        re.compile(
            r"(?:by\s+)?(?:the\s+|this\s+|next\s+)?\b(end\s+of\s+week|eow)\b",
            re.IGNORECASE,
        ),
        1,
        lambda m, sent: _friday_of_week(sent),
    ),
    (
        re.compile(
            r"(?:by\s+)?(?:the\s+|this\s+|next\s+)?\b(end\s+of\s+month|eom)\b",
            re.IGNORECASE,
        ),
        1,
        lambda m, sent: _end_of_month(sent),
    ),
    (
        re.compile(
            r"\bby\s+(" + "|".join(_MONTHS) + r")\s+(\d{1,2})(?:st|nd|rd|th)?\b",
            re.IGNORECASE,
        ),
        0,
        _month_day,
    ),
    (
        re.compile(
            r"\b(?:eod|cob|end\s+of\s+day|close\s+of\s+business)\b",
            re.IGNORECASE,
        ),
        0,
        lambda m, sent: sent,
    ),
    (
        re.compile(
            r"\bwithin\s+(\d+|" + "|".join(_NUMBER_WORDS) + r")"
            r"\s+(?:business\s+)?days?\b",
            re.IGNORECASE,
        ),
        0,
        _within,
    ),
    (
        re.compile(r"\bby\s+tomorrow\b", re.IGNORECASE),
        0,
        lambda m, sent: sent + datetime.timedelta(days=1),
    ),
)

# A full stop, a question mark, an exclamation mark, or a line break.
# Nothing else -- not a semicolon, not a colon, not a dash, not a comma --
# and the character counts wherever it falls, abbreviation or not.
_SENTENCE_END = re.compile(r"[.?!\r\n]")


def _dates_in(body: str, sent: datetime.date) -> dict[str, int]:
    """Each distinct date the body names, and the leftmost form that names it.

    A message naming one date in two forms is one row; a message naming
    two dates in one sentence is two. Keyed by the date, so the collapse
    and the split both fall out of the same dict.
    """

    found: dict[str, int] = {}
    for pattern, group, resolve in _FORMS:
        for match in pattern.finditer(body):
            due = resolve(match, sent)
            if due is None:
                continue
            key = due.isoformat()
            where = match.start(group)
            if key not in found or where < found[key]:
                found[key] = where
    return found


def main() -> None:
    if WINDOW_DAYS is None:
        raise SystemExit(
            "WINDOW_DAYS is unmeasured. Fix the window against the recorded "
            "world (datasets/merrick/measure_candidates.py --days N) and "
            "write the same window into instruction.md and tests/verify.py. "
            "A guessed window produces a real answer key over an imaginary "
            "corpus, and every row is wrong together while every row-level "
            "check stays green."
        )
    cutoff = WINDOW_DAYS * 86_400

    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    rows = []
    read = 0
    per_message: dict[str, list[int]] = {}
    bodies: dict[str, str] = {}
    for message_id, sender, when, body in gmail.execute(
        "SELECT message_id, sender, time, body FROM messages"
    ):
        if when >= cutoff:
            continue
        # Counted inside the window only. Requiring the whole record here
        # is what turned a comparable task into three rollouts with no
        # deliverable at all: the bound has to apply to the work, not only
        # to the answer.
        read += 1
        sent = (epoch + datetime.timedelta(seconds=when)).date()
        found = _dates_in(body, sent)
        if not found:
            continue
        if len(set(found.values())) != len(found):
            # Two dates reported at the same character would collapse the
            # row key, which is the one defect the key exists to prevent.
            # No pair of these forms can start at the same character, so
            # this firing means a form was added that overlaps another and
            # the instruction owes the reader a tie-break.
            raise SystemExit(
                f"{message_id}: two due dates share a character position "
                f"{sorted(found.items())} -- the row key (ref, at) is not "
                "unique, and the ceiling would sit below 1.0."
            )
        bodies[message_id] = body
        per_message[message_id] = sorted(found.values())
        for due, where in found.items():
            rows.append(
                {
                    "ref": message_id,
                    "at": where,
                    "due_date": due,
                    "author": people[sender],
                    "sent_date": sent.isoformat(),
                }
            )

    rows.sort(key=lambda row: (row["ref"], row["at"]))

    pairs = 0
    for message_id, positions in per_message.items():
        body = bodies[message_id]
        for i, first in enumerate(positions):
            for second in positions[i + 1 :]:
                if not _SENTENCE_END.search(body[first:second]):
                    pairs += 1

    # Every weekday, including the ones nothing falls on. Emitting only
    # the weekdays that occur would make "does a zero belong in the
    # object?" a judgement the instruction never settles, and an answer
    # can be marked wrong for guessing it either way.
    by_weekday = {name: 0 for name in _WEEKDAY_NAMES}
    by_author: dict[str, int] = defaultdict(int)
    for row in rows:
        due = datetime.date.fromisoformat(row["due_date"])
        by_weekday[_WEEKDAY_NAMES[due.weekday()]] += 1
        by_author[row["author"]] += 1

    OUT.write_text(
        json.dumps(
            {
                "messages_read": read,
                "rows_total": len(rows),
                "messages_with_dates": len(per_message),
                "same_sentence_pairs": pairs,
                "distinct_authors": len(by_author),
                # Most rows, then the earlier name -- `max` breaks a tie
                # the other way and the instruction says earlier first.
                "top_author": min(by_author, key=lambda name: (-by_author[name], name))
                if by_author
                else None,
                "due_weekday_counts": by_weekday,
                "dates": rows,
            },
            indent=1,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
