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


def _mail() -> list[tuple[int, str]]:
    path = STATE / "gmail.db"
    if not path.is_file():
        raise SystemExit(f"no gmail.db under {STATE}; build the bundle first")
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    rows = connection.execute("SELECT time, body FROM messages").fetchall()
    connection.close()
    return [(int(t), body or "") for t, body in rows]


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
        dead = "   <-- ADMITS NOTHING: a form_counts key that is a constant"
        print(
            f"  {name:14s} {occurrences:5d} occurrences, {carrying:4d} messages"
            f"{dead if occurrences == 0 else ''}"
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
