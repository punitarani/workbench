"""Every value `live-commitment-register`'s brief needs, for one window.

    WORKBENCH_STATE=out/merrick/bundle/state uv run python \
        datasets/merrick/measure_commitment_window.py --first-day 42 --last-day 88

This exists because filling a brief by hand is where this dataset's most
expensive defects have come from. Three in one session: a window measured
on a partial recording and never re-measured; per-form counts published as
prose that an agent then read as a specification it could not satisfy; and
a deadline rate quoted from a world that had since been re-recorded. Every
one was a true number in the wrong place, and none of them was caught by a
test, because a brief is prose and prose does not fail.

So the values come from one command, run against the corpus that ships,
and the screen refuses a window that cannot carry the task rather than
printing numbers for one that cannot.

What it deliberately does NOT print is a count per deadline form. Those are
measured here — you need them to choose which forms to admit — and they are
reported under a heading that says not to publish them. A count of the
answer's own composition is a specification: raw match counts over
overlapping patterns are not a partition, cannot be reproduced by anyone,
and a careful reader will spend its budget trying. A count of *excluded*
material is safe, and `off-sense-register` publishes those freely.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import os
import re
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

STATE = Path(os.environ.get("WORKBENCH_STATE", "out/merrick/bundle/state"))

# The rule comes from the SOLVER, imported rather than restated.
#
# It used to be restated here, with a comment explaining that a screen must
# be runnable against a task not yet written. The cost of that arrived
# twice. This file's own docstring records the first: it disagreed with
# what it screens for until 2026-08-23, when it was brought up to the
# sentence rule. The rule then gained four more conditions -- clause, not
# sentence; the day after the promise; the day attached; nobody else's
# clause between -- and this file stayed on the sentence rule and reported
# 25 rows for a window the solver reads as 19.
#
# A screen that measures a different rule than the grader chooses the
# window on numbers nobody will be scored against. Importing costs the
# ability to run this before `solve.py` exists, which has never once been
# needed; drifting costs the window.
#
# The window itself is NOT imported: `solve.py` names it inside a function
# so it stays importable unfilled, and this screen supplies its own from
# argv, which is the whole point of running it.
# `solve.py` reads `WORKBENCH_STATE` at import, so the default this file
# already computes is put in the environment first. Without it, importing
# this module raises `KeyError` before any test can set the variable --
# which is what happened, and what a collection error looks like when the
# import is the thing under test.
os.environ.setdefault("WORKBENCH_STATE", str(STATE))
sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parent
        / "tasks"
        / "live-commitment-register"
        / "solution"
    ),
)
import solve as _solve  # noqa: E402

OWNER = _solve._OWNER
STANDING_MINIMUM = _solve.STANDING_SERIES_MINIMUM
WORD_CEILING = 60_000
ROW_FLOOR = 12
SUPERSESSION_FLOOR = 0.15
_WEEKDAYS = _solve.WEEKDAYS

_commitment_in = _solve.commitment_in


def _token(text: str) -> str | None:
    return _solve.deadline_token(text)


def _due(said_on: dt.date, token: str) -> dt.date:
    if token == "eod":
        return said_on
    if token == "tomorrow":
        day = said_on + dt.timedelta(days=1)
        while day.weekday() >= 5:
            day += dt.timedelta(days=1)
        return day
    if token == "end of week":
        return said_on + dt.timedelta(days=(4 - said_on.weekday()) % 7)
    ahead = (_WEEKDAYS.index(token) - said_on.weekday()) % 7
    return said_on + dt.timedelta(days=ahead or 7)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--first-day", type=int, required=True)
    parser.add_argument("--last-day", type=int, required=True)
    args = parser.parse_args(argv)

    path = STATE / "meetings.db"
    if not path.is_file():
        raise SystemExit(f"no meetings.db under {STATE}; build the bundle first")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    zone = ZoneInfo(meta["timezone"])
    epoch = dt.datetime.fromisoformat(meta["epoch"]).astimezone(zone)

    low = args.first_day * 86_400
    high = (args.last_day + 1) * 86_400 - 1
    window = {
        i: (s, t)
        for i, s, t in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= s <= high
    }
    counted = collections.Counter(title for _s, title in window.values())
    standing = {t for t, n in counted.items() if n >= STANDING_MINIMUM}
    window = {i: r for i, r in window.items() if r[1] in standing}
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in window
    ]
    connection.close()

    people = dict(
        sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True).execute(
            "SELECT person_id, name FROM people"
        )
    )
    words = sum(len((t[3] or "").split()) for t in turns)
    dates = {(epoch + dt.timedelta(seconds=s)).date() for s, _t in window.values()}
    first = epoch + dt.timedelta(days=args.first_day)
    last = epoch + dt.timedelta(days=args.last_day)

    said: dict[tuple[str, str], list] = collections.defaultdict(list)
    for meeting_id, position, speaker, text in turns:
        # The promise and the date must be in ONE SENTENCE, which is the
        # rule the task grades and this file's own first law. Asking
        # whether a turn holds an owner form *somewhere* and a deadline
        # *somewhere* is a different question in a 71-word turn, and it is
        # the question this screen was asking: on days 1-25 of v7 it
        # counted 21 rows where the solver's oracle holds 15, a 40%
        # overstatement in the number the ROW FLOOR is checked against.
        # A window the screen called usable at 13 could build 9 and be
        # refused, one step after the decision that caused it.
        token = _commitment_in(text or "")
        if token is None:
            continue
        started, title = window[meeting_id]
        said[(speaker, title)].append((started, position, meeting_id, token))

    rows, superseded, moved = [], 0, 0
    for (speaker, title), occasions in said.items():
        occasions.sort()
        superseded += len({o[2] for o in occasions}) - 1
        first_due = _due(
            (epoch + dt.timedelta(seconds=occasions[0][0])).date(), occasions[0][3]
        )
        started, _p, _m, token = occasions[-1]
        due = _due((epoch + dt.timedelta(seconds=started)).date(), token)
        rows.append((people.get(speaker, speaker), title, due))
        if len({o[2] for o in occasions}) > 1 and first_due != due:
            moved += 1

    print("VALUES FOR THE BRIEF — paste these\n")
    print(f"  window first day   **{first:%A %-d %B %Y}**")
    print(f"  window last day    **{last:%A %-d %B %Y}**")
    print(f"  working days       **{len(dates)}**")
    print(f"  standing meetings  **{len(window)}**")
    share = moved / len(rows) if rows else 0.0
    print(
        f"  supersession share  On this window, {share:.0%} of the rows carry a\n"
        f"                      due date that differs between the person's first\n"
        f"                      statement and their last"
    )

    print("\nFOR YOUR EYES — do NOT publish these counts in the brief")
    print("  (a count of the answer's own composition reads as a specification;")
    print("   raw counts over overlapping patterns are not a partition)")
    commitment = [t for t in turns if OWNER.search(t[3] or "")]
    # Named, not indexed. These used to be `_COMPILED[1]`, `_COMPILED[3]`
    # and so on into a table this file owned; the table now lives in the
    # solver, where the compounds come first and the ordinals mean
    # something else entirely. A positional index into somebody else's
    # table is a silent mislabel waiting for that table to grow.
    for name, pattern in (
        ("end of day", re.compile(_solve._EOD, re.IGNORECASE)),
        ("tomorrow", re.compile(r"\btomorrow\b", re.IGNORECASE)),
        (
            "end of week",
            re.compile(
                r"\b(?:EOW|end[\s\-]+of[\s\-]+(?:the[\s\-]+)?week)\b", re.IGNORECASE
            ),
        ),
        (
            "compound EOD-tomorrow",
            re.compile(_solve._EOD + r"[\s\-]+tomorrow\b", re.IGNORECASE),
        ),
        ("a named weekday", re.compile("|".join(_WEEKDAYS), re.IGNORECASE)),
    ):
        n = sum(1 for t in commitment if pattern.search(t[3] or ""))
        print(f"    {name:<24s}{n:5d}")

    print("\nSCREENS")
    verdict = "usable" if words <= WORD_CEILING else "OVER THE WORD CEILING"
    print(f"  words            {words:>7,d}   {verdict}")
    print(
        f"  rows             {len(rows):>7d}   "
        f"{'usable' if len(rows) >= ROW_FLOOR else 'UNDER THE ROW FLOOR'}"
    )
    print(
        f"  supersession     {share:>7.0%}   "
        f"{'usable' if share >= SUPERSESSION_FLOOR else 'UNDER THE FLOOR'}"
    )
    guess = collections.Counter(d for _o, _t, d in rows)
    if guess:
        top, n = guess.most_common(1)[0]
        print(
            f"  guessing floor   {n / len(rows):>7.0%}   the commonest single due "
            f"date, reachable with no reading"
        )
    print(f"  superseded_count {superseded:>7d}   the oracle's value")
    bad = words > WORD_CEILING or len(rows) < ROW_FLOOR or share < SUPERSESSION_FLOOR
    if bad:
        print("\n  REFUSED: this window cannot carry the task. Move it.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
