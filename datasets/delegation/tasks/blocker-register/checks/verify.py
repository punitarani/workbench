"""An independent derivation of the blocker register.

Transcribed from `instruction.md` and never from `solution/solve.py`.

The independence is in the route, not the wording:

  * the solver accumulates rooms into a SET per (owner, series) and takes
    `min`/`max` of the dates afterwards; this keeps a running earliest and
    latest as it walks, and counts rooms with a dict. An off-by-one or a
    duplicate in either is not shared.
  * the solver decides the standing series with a dict of date sets; this
    counts distinct days by sorting and comparing neighbours.
  * the rule itself comes from `blocked_rule_check`, which reaches the same
    sentence by walking word tokens where the solver's rule spans
    characters.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import blocked_rule as _names_source  # noqa: E402
import blocked_rule_check as checker  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])

_STATED: dict[str, tuple[str, ...]] = {
    "## What counts as a blocker": (
        "the speaker says **they** are stuck",
        "No other subject stands between the speaker and the complaint",
        "A question is not one",
    ),
    "## What to produce": (
        "the date they **first** said it in this standing meeting",
        "the date they **last** said it",
        "how many **meetings** of this series they said it in",
    ),
    "## The window and the meetings": ("three or more days",),
}

_SERIES_MINIMUM = 3
_WINDOW_LAST_DAY = 134


def _insists(brief: str) -> None:
    for heading, phrases in _STATED.items():
        start = brief.index(heading)
        end = brief.find("\n## ", start + 1)
        section = " ".join(brief[start : end if end > 0 else len(brief)].split())
        for phrase in phrases:
            flat = " ".join(phrase.split())
            if flat not in section:
                raise SystemExit(
                    f"MISMATCH {heading}: the brief no longer says {flat!r}, "
                    "which this file's derivation assumes"
                )


def main() -> int:
    brief = (Path(__file__).resolve().parent.parent / "instruction.md").read_text()
    _insists(brief)

    meetings = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    epoch = datetime.datetime.fromisoformat(
        dict(meetings.execute("SELECT key, value FROM meta"))["epoch"]
    )
    people = dict(
        sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True).execute(
            "SELECT person_id, name FROM people"
        )
    )
    names = list(_names_source.roster(STATE))
    last_second = (_WINDOW_LAST_DAY + 1) * 86_400 - 1

    rooms = [
        (mid, started, title)
        for mid, started, title in meetings.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if 0 <= started <= last_second
    ]
    # Distinct days counted by sorting and comparing neighbours rather than
    # by set membership, so a duplicate handled wrongly on one side shows up
    # as a disagreement.
    by_title: dict[str, list] = {}
    for _mid, started, title in rooms:
        by_title.setdefault(title, []).append(
            (epoch + datetime.timedelta(seconds=started)).date()
        )
    standing = set()
    for title, dates in by_title.items():
        dates.sort()
        distinct = 1 + sum(1 for a, b in zip(dates, dates[1:]) if b != a)
        if distinct >= _SERIES_MINIMUM:
            standing.add(title)

    room = {
        mid: (started, title) for mid, started, title in rooms if title in standing
    }
    turns = [
        row
        for row in meetings.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in room
    ]
    meetings.close()

    # A running earliest, latest and room tally, kept as the walk proceeds
    # rather than collected and reduced afterwards.
    seen: dict[tuple[str, str], dict] = {}
    for mid, _position, speaker, text in turns:
        if not checker.blocked_in(text or "", names):
            continue
        started, title = room[mid]
        when = (epoch + datetime.timedelta(seconds=started)).date()
        key = (people.get(speaker, speaker), title)
        entry = seen.setdefault(
            key,
            {"first": when, "last": when, "rooms": {}, "at_first": mid, "at_last": mid},
        )
        entry["rooms"][mid] = True
        if when < entry["first"]:
            entry["first"], entry["at_first"] = when, mid
        if when > entry["last"]:
            entry["last"], entry["at_last"] = when, mid

    stuck = [
        {
            "owner": owner,
            "meeting": title,
            "first_raised": entry["first"].isoformat(),
            "last_raised": entry["last"].isoformat(),
            "raised_count": len(entry["rooms"]),
            "first_meeting_id": entry["at_first"],
            "last_meeting_id": entry["at_last"],
        }
        for (owner, title), entry in seen.items()
    ]
    stuck.sort(key=lambda entry: (entry["meeting"], entry["owner"]))

    print(
        json.dumps(
            {
                "meetings_read": len(room),
                "turns_read": len(turns),
                "distinct_owners": len({entry["owner"] for entry in stuck}),
                "blockers": stuck,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
