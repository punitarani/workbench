"""The register of what this firm's partners told other people to do.

    WORKBENCH_STATE=out/delegation/bundle/state uv run python \
        datasets/delegation/tasks/assignment-revision-register/solution/solve.py

The sibling of the commitment registers on merrick, and deliberately the
OTHER half of the same problem. Those read `I'll ...` and ask what the
speaker took on. This reads `Mira will ...` and asks what the speaker
handed to somebody else -- so the owner of a row is never the person who
said the words, and a reader who keys on the speaker gets every row wrong
while finding every turn.

The rule itself is `datasets/delegation/assignment_rule.py`, which is
shared rather than inlined. It and its independent checker agree on 10,211
items across six corpora; copying it into this file would fork that
agreement on the first correction either side received.
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

import assignment_rule as rule  # noqa: E402
import promise_rule  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("assignment_register.json")

# Same threshold and the same reason as the commitment registers: standing
# series recur 4-32 times per window and one-offs 1 or 2, so any cut in 3..4
# separates them. A one-off is a key with one meeting in it -- nothing can
# supersede, and the key is a free-text title the agent must reproduce
# exactly.
STANDING_SERIES_MINIMUM = 3


def _window() -> tuple[int, int]:
    """The recorded epoch, whole, as a pair of second offsets.

    Named `WINDOW_FIRST_DAY` / `WINDOW_LAST_DAY` because `build_tasks` reads
    those names off the source to tell its verifier which window to
    re-derive. A solver that states its window some third way is refused,
    and rightly: a window nobody can read is a window nobody can check.

    This world is 135 recorded days and the register covers all of them.
    The commitment registers on merrick were cut to shorter windows to move
    a score; this one has no such need yet, and shortening it would only
    shorten the chains -- measured there: at 42 days the median person
    revises once and a frontier model scores 1.000.
    """

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
    connection = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    epoch, _zone = _epoch(connection)
    names = rule.roster(STATE)

    low, high = _window()
    window = {
        meeting_id: (started, title)
        for meeting_id, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    }
    standing = {
        title
        for title, count in collections.Counter(
            title for _started, title in window.values()
        ).items()
        if count >= STANDING_SERIES_MINIMUM
    }
    window = {
        meeting_id: row for meeting_id, row in window.items() if row[1] in standing
    }
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in window
    ]
    connection.close()

    said: dict[tuple[str, str], list] = {}
    for meeting_id, position, _speaker, text in turns:
        found = rule.assignment_in(text or "", names)
        if found is None:
            continue
        owner, token = found
        started, title = window[meeting_id]
        said.setdefault((owner, title), []).append(
            (started, position, meeting_id, token)
        )

    register, superseded = [], 0
    for (owner, title), occasions in said.items():
        occasions.sort()
        # The unit is the meeting, not the turn: a colleague handed the same
        # work twice inside one room was handed it once.
        replaced = len({row[2] for row in occasions}) - 1
        superseded += replaced
        started, _position, meeting_id, token = occasions[-1]
        first_started, _fp, _fm, first_token = occasions[0]
        moment = epoch + dt.timedelta(seconds=started)
        first_moment = epoch + dt.timedelta(seconds=first_started)
        register.append(
            {
                "owner": owner,
                "meeting": title,
                "due": promise_rule.due_date(moment.date(), token).isoformat(),
                "first_due": promise_rule.due_date(
                    first_moment.date(), first_token
                ).isoformat(),
                "superseded": replaced,
                "meeting_id": meeting_id,
                "said_at": moment.isoformat(),
            }
        )
    register.sort(key=lambda row: (row["meeting"], row["owner"]))

    OUT.write_text(
        json.dumps(
            {
                "meetings_read": len(window),
                "turns_read": len(turns),
                "distinct_owners": len({row["owner"] for row in register}),
                "superseded_count": superseded,
                "assignments": register,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
