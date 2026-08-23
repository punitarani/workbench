"""Which week the promise register should read, and what its table may say.

    uv run python datasets/merrick/measure_promise_week.py

The deadline-week brief takes a Monday and grades every promise form its
table admits. Two things have to be measured before that table is fixed,
and both have already been got wrong in this dataset:

**A row of the table that admits nothing.** Measured over 2,717 mail
messages here: `end of month`, `end of the month` and `EOM` occur **zero**
times between them, so that row exercises no rule and its `form_counts`
key is a constant. The screen prints every row's count so a dead one is
visible before it ships.

**The wording the firm actually writes.** The brief warns that in a
comparable firm's mail the *article* form (`end of the week`) appeared
fifteen times and the bare form not once. Here it is the other way round —
bare 172, article 0 — so the table's bare-only choice is right for this
corpus and wrong for that one. Whichever way it falls, the table has to
match the count, or a rule requiring a wording the corpus writes once
where it writes another thirty-four times admits one instance of
thirty-five and scores the rest as inventions.

Then the week itself. A week is chosen for row count *and* for how many
of the forms it exercises: a week carrying fifty rows of one form tests
one row of the table.
"""

from __future__ import annotations

import argparse
import datetime
import os
import re
import sqlite3
from pathlib import Path

STATE = Path(os.environ.get("WORKBENCH_STATE", "out/merrick/bundle/state"))

# Kept in step with EPOCH_START in the workplace definition. The served
# meta table carries it too, but reading that needs a connection this
# screen does not otherwise open, and this dataset's epoch is fixed.
EPOCH = datetime.date(2026, 1, 5)

# One pattern per row of the brief's table, in the brief's own order.
FORMS: dict[str, str] = {
    "by weekday": (
        r"\bby\s+(?:this\s+|next\s+)?"
        r"(?:Monday|Tuesday|Wednesday|Thursday|Friday)\b"
    ),
    "end of week": r"\bend\s+of\s+week\b|\bEOW\b",
    "end of month": r"\bend\s+of\s+month\b|\bEOM\b",
    "by date": (
        r"\bby\s+(?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2}"
    ),
    "end of day": (r"\bend\s+of\s+day\b|\bEOD\b|\bCOB\b|\bclose\s+of\s+business\b"),
    "within days": (
        r"\bwithin\s+(?:\d+|a|an|one|two|three|four|five|ten)\s+"
        r"(?:business\s+)?days?\b"
    ),
    "by tomorrow": r"\bby\s+tomorrow\b",
}

# Wordings the table does *not* admit. Each is a decision the brief has to
# state out loud, because leaving it unsaid is a coin flip the reader
# cannot win.
VARIANTS: dict[str, str] = {
    "end of THE week": r"\bend\s+of\s+the\s+week\b",
    "end of THE month": r"\bend\s+of\s+the\s+month\b",
    "end of THE day": r"\bend\s+of\s+the\s+day\b",
    "end-of-week": r"\bend-of-week\b",
    "end-of-day": r"\bend-of-day\b",
    "by Saturday/Sunday": r"\bby\s+(?:this\s+|next\s+)?(?:Saturday|Sunday)\b",
    "by <Mon>. <day>": (
        r"\bby\s+(?:Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept?|Oct|Nov|Dec)\.?\s+\d{1,2}"
    ),
}


# A row does not have to admit *nothing* to be worthless. It has to admit
# too little for a reader to be wrong about it.
#
# This screen used to flag only an exact zero, and `by date` walked
# straight past it: **5 occurrences across 3 of 2,717 messages** in a
# six-month record, which is nothing in any window a task can use, and the
# screen printed it beside `by weekday` at 106 messages without comment.
# On the re-recorded world the same row is a true zero — so the defect was
# always there and the guard only noticed once the corpus got poorer.
#
# It is the same mistake the fidelity band gate made and had fixed the same
# week: refusing `observed == 0` let a metric through at 0.000315. A check
# that fires only on exactly nothing is a check calibrated to the one case
# somebody already thought of.
_DEAD = 10
"""Messages in the whole record below which a row grades noise.

Ten because a task windows a fraction of the record: a row carried by
three messages in six months is carried by none in the ten-day window the
in-band precedent settled on, and a `form_counts` key nobody can populate
is a constant an agent scores by writing 0."""


def _verdict(carrying: int) -> str:
    if carrying == 0:
        return "   <-- ADMITS NOTHING: a form_counts key that is a constant"
    if carrying < _DEAD:
        return (
            f"   <-- EFFECTIVELY ABSENT: {carrying} message(s) in the whole "
            "record grades noise in any window"
        )
    return ""


def _mail() -> list[tuple[int, str]]:
    return [(when, body) for when, body, _, _ in _mail_full()]


def _mail_full() -> list[tuple[int, str, str, str]]:
    """Time, body, thread and sender.

    `_mail` kept only the first two, which is all the table and the week
    need. The candidate-ratio section below needs to know who wrote a
    promise and whether they came back on it, and that is a property of
    later traffic in the same thread.
    """

    path = STATE / "gmail.db"
    if not path.is_file():
        raise SystemExit(f"no gmail.db under {STATE}; build the bundle first")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = connection.execute(
        "SELECT time, body, thread_id, sender FROM messages"
    ).fetchall()
    connection.close()
    return [(int(t), body or "", thread, sender) for t, body, thread, sender in rows]


# A promise is a first-person undertaking and a date in ONE sentence. Over a
# whole message the two come apart: this dataset already retired a rule that
# paired a speaker with a deadline across a 71-word turn.
_OWNER = re.compile(r"\b(?:I'?ll|I will|I can|I'?m|let me|I'?d|I have)\b", re.I)
_SENTENCE = re.compile(r"(?<=[.?!;])\s+")


def _ratio_section(compiled: dict[str, re.Pattern[str]]) -> None:
    """What a reader who reports everything already scores.

    The register's rows are promises; its candidates are whatever a dumper
    would submit. **Which pool the report declares decides the floor it
    measures**, and declaring the wider one flatters the task: against
    every mail message this reads one thing, and against the messages that
    carry a date -- the set a dumper actually submits, since the report
    asks for dated promises and filtering to dates is one cheap pass --
    it reads far worse. Both are printed so the choice cannot be made by
    omission.

    Then the rule itself. `followed_up` is the field this design is proud
    of: it cannot be read off the message carrying the promise, only out of
    later traffic in the same thread. As the *rule* rather than a field it
    is much stronger, and the minority class is the KEPT promise, not the
    broken one.
    """

    mail = _mail_full()
    threads: dict[str, list[tuple[int, str]]] = {}
    for when, _body, thread, sender in mail:
        threads.setdefault(thread, []).append((when, sender))

    def dated(body: str) -> bool:
        return any(rx.search(body) for rx in compiled.values())

    def promises(body: str) -> bool:
        return any(
            _OWNER.search(part) and dated(part) for part in _SENTENCE.split(body)
        )

    carrying = [m for m in mail if dated(m[1])]
    promised = [m for m in mail if promises(m[1])]
    kept = [
        m
        for m in promised
        if any(later > m[0] and who == m[3] for later, who in threads[m[2]])
    ]
    broken = [m for m in promised if m not in kept]

    def show(label: str, rows: int, pool: int, note: str = "") -> None:
        share = rows / pool if pool else 0.0
        f1 = 2 * share / (share + 1) if share else 0.0
        print(f"  {label:<46}{rows:>5}{share:>8.3f}{f1:>11.3f}{note}")

    print("\nwhat reporting everything already scores")
    header = "rows / the pool the report declares"
    print(f"  {header:<46}{'rows':>5}{'ratio':>8}{'dumped F1':>11}")
    show(
        "every promise / every mail message", len(promised), len(mail), "   flattering"
    )
    show(
        "every promise / mail carrying a date",
        len(promised),
        len(carrying),
        "   <- the honest pool",
    )
    show("... promises never followed up", len(broken), len(carrying))
    show(
        "... promises the writer came back on",
        len(kept),
        len(carrying),
        "   <- minority class",
    )
    print(
        "  A dumper submits dated messages, not every message in the firm, so"
        "\n  the second line is the floor to believe. Under twelve rows the build"
        "\n  refuses outright, so read both columns."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top", type=int, default=5)
    args = parser.parse_args(argv)

    mail = _mail()
    compiled = {name: re.compile(rx, re.I) for name, rx in FORMS.items()}

    print(f"{len(mail)} mail messages\n")
    print("the table's rows, over the whole record")
    for name, rx in compiled.items():
        occurrences = sum(len(rx.findall(body)) for _, body in mail)
        carrying = sum(1 for _, body in mail if rx.search(body))
        print(
            f"  {name:14s} {occurrences:5d} occurrences, {carrying:4d} messages"
            f"{_verdict(carrying)}"
        )

    print("\nwordings the table excludes — each one a sentence the brief owes")
    for name, rx in VARIANTS.items():
        pattern = re.compile(rx, re.I)
        occurrences = sum(len(pattern.findall(body)) for _, body in mail)
        note = "" if occurrences else "   (moot here, but say so)"
        print(f"  {name:20s} {occurrences:5d}{note}")

    weeks: dict[datetime.date, dict[str, int]] = {}
    for seconds, body in mail:
        day = EPOCH + datetime.timedelta(days=seconds // 86_400)
        if day.weekday() >= 5:
            continue
        monday = day - datetime.timedelta(days=day.weekday())
        week = weeks.setdefault(monday, {"messages": 0, **dict.fromkeys(FORMS, 0)})
        week["messages"] += 1
        for name, rx in compiled.items():
            if rx.search(body):
                week[name] += 1

    print("\nby week — chosen for rows AND for how many rows of the table it")
    print("exercises, because fifty rows of one form tests one rule")
    ranked = sorted(
        (
            (sum(w[n] for n in FORMS), sum(1 for n in FORMS if w[n]), monday, w)
            for monday, w in weeks.items()
        ),
        reverse=True,
    )
    for rows, kinds, monday, week in ranked[: args.top]:
        present = ", ".join(n for n in FORMS if week[n])
        print(
            f"  {monday} ({monday:%-d %B}) — {week['messages']:3d} read, "
            f"~{rows:3d} rows, {kinds}/{len(FORMS)} forms: {present}"
        )

    _ratio_section(compiled)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
