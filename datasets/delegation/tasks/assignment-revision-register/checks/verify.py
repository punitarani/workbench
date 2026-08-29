"""An independent derivation of the same register.

    WORKBENCH_STATE=out/delegation/bundle/state uv run python \
        datasets/delegation/tasks/assignment-revision-register/checks/verify.py

Everything here is transcribed from `instruction.md` -- the prose the agent
is graded against -- and nothing from `solution/solve.py`. Copying the
solver's expression reproduces its bug and then certifies that the two
agree; two published scores in this tree were the answer key wearing a
different hat, certified exactly that way.

The independence has to be at the level of ASSUMPTIONS, not code. A rule
and its checker in this tree once agreed across 10,211 items in six corpora
while both were wrong in four separate ways, because both were written from
the same brief and under-implemented the same clause of it. So:

  * the rule reaches its answer through regex over character spans; this
    reaches it through a walk over word tokens (`assignment_rule_check`);
  * the solver takes the last statement by SORTING the list and reading the
    end; this takes it by `max`, and the first by `min`, so an ordering bug
    there surfaces as a disagreement rather than being reproduced;
  * the solver counts distinct meetings with a set comprehension; this
    counts them by accumulating a dict, so an off-by-one in either is not
    shared.

Where more than one computation is defensible, this uses the one the solver
did not.
"""

from __future__ import annotations

import collections
import datetime
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import assignment_rule_check as checker  # noqa: E402
import assignment_rule as _names_source  # noqa: E402
import promise_rule_check as promise_check  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])

# Transcribed from the brief, and asserted rather than assumed. A phrase
# that leaves the instruction takes this derivation's justification with
# it, and the mismatch is the only signal that the two have drifted.
_STATED: dict[str, tuple[str, ...]] = {
    "## What counts as an assignment": (
        "the person speaking says **somebody else** will do",
        "names **when**",
        "in the same clause",
    ),
    "## Which one is live": (
        "the most recent one",
        "**even when the words are the same**",
    ),
    "## What to produce": (
        "how many **earlier** assignments this colleague was handed",
        "the date this colleague was **first** given",
        "against the meeting it was said in",
    ),
}

_SERIES_MINIMUM = 3


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
    meta = dict(meetings.execute("SELECT key, value FROM meta"))
    epoch = datetime.datetime.fromisoformat(meta["epoch"])
    names = _names_source.roster(STATE)
    checker.use_roster(names.values()) if hasattr(checker, "use_roster") else None

    rooms = list(meetings.execute("SELECT meeting_id, started, title FROM meetings"))
    # Counted by accumulation rather than by Counter, so an off-by-one is
    # not shared with the solver.
    seen: dict[str, int] = {}
    for _mid, _started, title in rooms:
        seen[title] = seen.get(title, 0) + 1
    standing = {title for title, count in seen.items() if count >= _SERIES_MINIMUM}
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

    handed: dict[tuple[str, str], list] = collections.defaultdict(list)
    for mid, position, _speaker, text in turns:
        found = checker.assignment_in(text or "", names)
        if found is None:
            continue
        owner, token = found
        handed[(owner, room[mid][1])].append((room[mid][0], position, mid, token))

    register, discarded = [], 0
    for (owner, title), occasions in handed.items():
        last = max(occasions, key=lambda o: (o[0], o[1]))
        first = min(occasions, key=lambda o: (o[0], o[1]))
        # Distinct rooms, by accumulating a dict rather than by a set.
        counted: dict[str, bool] = {}
        for _s, _p, mid, _t in occasions:
            counted[mid] = True
        discarded += len(counted) - 1
        at = epoch + datetime.timedelta(seconds=last[0])
        began = epoch + datetime.timedelta(seconds=first[0])
        register.append(
            {
                "owner": owner,
                "meeting": title,
                "due": promise_check._resolve(at.date(), last[3]).isoformat(),
                "first_due": promise_check._resolve(
                    began.date(), first[3]
                ).isoformat(),
                "superseded": len(counted) - 1,
                "meeting_id": last[2],
                "said_at": at.isoformat(),
            }
        )
    register.sort(key=lambda row: (row["meeting"], row["owner"]))

    answer = {
        "meetings_read": len(room),
        "turns_read": len(turns),
        "distinct_owners": len({row["owner"] for row in register}),
        "superseded_count": discarded,
        "assignments": register,
    }
    print(json.dumps(answer, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
