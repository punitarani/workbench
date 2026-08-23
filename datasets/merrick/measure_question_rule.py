"""Which tightening the unanswered-question register should adopt, measured.

    WORKBENCH_STATE=<state> uv run python \
        datasets/merrick/measure_question_rule.py --window-days 30

The task as staged admits **a third of its own candidate pool** — 34 rows
against `questions_read` 102 on the probe oracle, which is a dumped row F1
of 0.500 and a measured dump floor of 0.556, the highest of this dataset's
three built tasks and 0.044 under the line where the build warns.

That is not a grading fault. A third of the questions in this firm go
unanswered, so "the unanswered ones" is not a minority of the pool, and
lowering the ratio means a rule that picks a minority **of the
unanswered**. Recounting candidates as "messages read" rather than
"questions asked" would lower the ratio on paper while a dumper's real
strategy is still to report every question — the metric lying rather than
the task improving.

This prints each candidate tightening's row count, its share of the pool,
and the row F1 a reader who reports every question would score. It does
not choose. The reason it exists is that the yields were first measured on
a dead world with a pattern written for a note rather than with the task's
own reply test, and carrying those numbers forward is the mistake this
dataset has paid for repeatedly.

**Read the ratio, not the row count.** A tightening that reaches 0.10 with
14 rows is worse than one that reaches 0.13 with 40: under twelve rows the
build refuses outright, because a register that thin cannot score
partially.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sqlite3
from collections import defaultdict
from pathlib import Path


def _state() -> Path:
    state = os.environ.get("WORKBENCH_STATE")
    if not state:
        raise SystemExit("set WORKBENCH_STATE to a bundle's state directory")
    return Path(state)


def _working_days(start: datetime.date, count: int) -> datetime.date:
    day, moved = start, 0
    while moved < count:
        day += datetime.timedelta(days=1)
        if day.weekday() < 5:
            moved += 1
    return day


def measure(state: Path, window_days: int, response_days: int = 3) -> None:
    gmail = sqlite3.connect(f"file:{state / 'gmail.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(gmail.execute("SELECT key, value FROM meta"))["epoch"]
    )

    def on(seconds: int) -> datetime.date:
        return (epoch + datetime.timedelta(seconds=seconds)).date()

    # To only, exactly as the solver reads it: cc is copied, not asked.
    addressed: dict[str, set[str]] = defaultdict(set)
    for message_id, person_id, kind in gmail.execute(
        "SELECT message_id, person_id, kind FROM recipients"
    ):
        if kind == "to":
            addressed[message_id].add(person_id)

    threads: dict[str, list[tuple[int, str, str]]] = defaultdict(list)
    messages: dict[str, tuple[str, str, int, str]] = {}
    for message_id, thread_id, sender, when, body in gmail.execute(
        "SELECT message_id, thread_id, sender, time, body FROM messages"
    ):
        threads[thread_id].append((when, sender, message_id))
        messages[message_id] = (thread_id, sender, when, body or "")
    for turns in threads.values():
        turns.sort()

    cutoff = window_days * 86_400
    questions, unanswered = [], []
    for message_id, (thread_id, _sender, when, body) in messages.items():
        if when >= cutoff or "?" not in body or not addressed.get(message_id):
            continue
        to = addressed[message_id]
        questions.append(message_id)
        due = _working_days(on(when), response_days)
        if not any(
            later_sender in to and later_when > when and on(later_when) <= due
            for later_when, later_sender, _ in threads[thread_id]
        ):
            unanswered.append(message_id)

    pool = len(questions)
    if not pool:
        raise SystemExit(f"no questions inside {window_days} days — widen the window")

    def moved_on(message_id: str) -> bool:
        thread_id, _, when, _ = messages[message_id]
        return any(later > when for later, _, _ in threads[thread_id])

    def asked_again(message_id: str) -> bool:
        thread_id, sender, when, _ = messages[message_id]
        return any(
            other_sender == sender and other_when > when
            for other_when, other_sender, _ in threads[thread_id]
        )

    def two_marks(message_id: str) -> bool:
        return messages[message_id][3].count("?") >= 2

    def one_addressee(message_id: str) -> bool:
        return len(addressed[message_id]) == 1

    print(f"window {window_days} days, response {response_days} working days")
    print(f"  questions asked (the pool a dumper reports): {pool}")
    print(f"  unanswered: {len(unanswered)}\n")
    print(f"  {'rule':<44}{'rows':>6}{'ratio':>8}{'dumped F1':>11}")
    rules = (
        ("every unanswered question (as staged)", lambda _m: True),
        ("... the thread continued without them", moved_on),
        ("... the asker asked again in the thread", asked_again),
        ("... two or more question marks", two_marks),
        ("... addressed to exactly one person", one_addressee),
    )
    for label, keep in rules:
        rows = [m for m in unanswered if keep(m)]
        share = len(rows) / pool
        f1 = 2 * share / (share + 1) if share else 0.0
        note = ""
        if len(rows) < 12:
            note = "  UNDER THE ROW FLOOR — the build refuses this"
        elif share <= 0.12:
            note = "  <- inside the tenth the law asks for"
        print(f"  {label:<44}{len(rows):>6}{share:>8.3f}{f1:>11.3f}{note}")
    print(
        "\n  Read the ratio, not the row count: a rule reaching 0.10 with 11 rows"
        "\n  is refused, and one reaching 0.13 with 40 is not."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--window-days", type=int, required=True)
    parser.add_argument("--response-days", type=int, default=3)
    args = parser.parse_args()
    measure(_state(), args.window_days, args.response_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
