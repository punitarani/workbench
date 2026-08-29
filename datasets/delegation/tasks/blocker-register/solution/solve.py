"""The register of what is not moving, and for how long.

    WORKBENCH_STATE=out/delegation/bundle/state uv run python \
        datasets/merrick/tasks/blocker-register/solution/solve.py

The third family on this world and the first with no deadline in it. The
commitment registers ask what somebody promised and when; this asks what
they have been stuck on, when they first said so, when they last said so,
and how many rooms in between they said it again.

**Why that is harder than it sounds.** A commitment carries its own date --
"by Thursday" is in the sentence. A complaint carries nothing. Its dates
come from the MEETINGS, so a reader who finds one complaint has no way to
tell whether it is the first or the ninth; the only way to place it is to
have read every other room in the series. There is no local evidence at all.

The rule lives in `datasets/merrick/blocked_rule.py`, shared rather than
inlined: it and its independent checker agree on 4,998 turns across two
worlds, and a copy here would fork that agreement on the first correction.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import os
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import blocked_rule as rule  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("blocker_register.json")

STANDING_SERIES_MINIMUM = 3


def _window() -> tuple[int, int]:
    """The recorded epoch, whole, as a pair of second offsets."""

    WINDOW_FIRST_DAY = 0
    WINDOW_LAST_DAY = 134
    return WINDOW_FIRST_DAY * 86_400, (WINDOW_LAST_DAY + 1) * 86_400 - 1


def _epoch(connection: sqlite3.Connection) -> tuple[dt.datetime, ZoneInfo]:
    row = dict(connection.execute("SELECT key, value FROM meta"))
    return (
        dt.datetime.fromisoformat(row["epoch"]),
        ZoneInfo(row.get("timezone", "America/New_York")),
    )


def main() -> int:
    low, high = _window()
    connection = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    epoch, _zone = _epoch(connection)
    people = dict(
        sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True).execute(
            "SELECT person_id, name FROM people"
        )
    )
    names = list(rule.roster(STATE))

    window = {
        meeting_id: (started, title)
        for meeting_id, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    }
    # DAYS, not meetings: the brief says a title must appear on three or
    # more days, and a room used twice in one day is one day.
    days: dict[str, set] = {}
    for started, title in window.values():
        days.setdefault(title, set()).add(
            (epoch + dt.timedelta(seconds=started)).date()
        )
    standing = {t for t, seen in days.items() if len(seen) >= STANDING_SERIES_MINIMUM}
    window = {i: row for i, row in window.items() if row[1] in standing}

    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in window
    ]
    connection.close()

    raised: dict[tuple[str, str], set] = collections.defaultdict(set)
    for meeting_id, _position, speaker, text in turns:
        if not rule.blocked_in(text or "", names):
            continue
        raised[(people.get(speaker, speaker), window[meeting_id][1])].add(meeting_id)

    register = []
    for (owner, title), rooms in raised.items():
        ordered = sorted(rooms, key=lambda m: window[m][0])
        when = [
            (epoch + dt.timedelta(seconds=window[m][0])).date() for m in ordered
        ]
        register.append(
            {
                "owner": owner,
                "meeting": title,
                "first_raised": when[0].isoformat(),
                "last_raised": when[-1].isoformat(),
                "raised_count": len(rooms),
                "first_meeting_id": ordered[0],
                "last_meeting_id": ordered[-1],
            }
        )
    register.sort(key=lambda row: (row["meeting"], row["owner"]))

    OUT.write_text(
        json.dumps(
            {
                "meetings_read": len(window),
                "turns_read": len(turns),
                "distinct_owners": len({row["owner"] for row in register}),
                "blockers": register,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
