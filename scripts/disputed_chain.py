"""Build the evidence for one disputed row of a DATE-LESS chain register.

    uv run python scripts/disputed_chain.py --dataset delegation \
        --task blocker-register \
        --row 'Fionnuala Doherty | Billing and WIP review | 2026-03-09 | 2026-03-09' \
        --out /tmp/row.json

`disputed.py` serves the commitment family and cannot serve this one. It
asks the rule for a token and resolves a date from it, and this family's
rule returns a BOOLEAN -- being stuck carries no day. Pointing it at a
blocker row fails at `owner, group, held = row.split("|")`, because the key
here holds four parts rather than three.

That is worth naming rather than patching around: the adjudication path
existed, was documented, and **could not be called for a whole family**.
Nothing errored until somebody tried, five certified-blocking rows in.

**The evidence unit is the CHAIN, not a sentence.** What is disputed about
one of these rows is never a date inside a clause. It is where the chain
starts, where it ends, and how many meetings it spans -- three facts that
only exist across turns. A judge shown the turn the key cites can confirm
that turn and leave the row wrong anyway, which is the failure the sibling
script's own docstring records paying for once already.

**The net is deliberately wider than the rule.** Every turn by this speaker
in this series that contains any stuck phrase at all is shown, each marked
with whether the rule admitted it. A judge reading the raw text can then say
the rule missed a turn or invented one -- a verdict the rule cannot reach
about itself. Showing only what the rule admitted is the circular check that
certified two answer keys in this tree as model failures.
"""

from __future__ import annotations

import argparse
import datetime as dt
import importlib
import json
import re
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parents[1]

# The over-broad net. Asserted as a superset of the rule's own phrase list
# and checked against it below, so it cannot silently drift narrower than
# the thing it is supposed to contain.
_NET = re.compile(
    r"blocked|waiting|held up|stuck|can'?t (?:move|proceed|close|sign|finish)"
    r"|pending|pend|hold|pause|await",
    re.IGNORECASE,
)


def _window(solver: Path) -> tuple[int, int]:
    text = solver.read_text()
    first = int(re.search(r"^\s*WINDOW_FIRST_DAY\s*=\s*(\d+)", text, re.M).group(1))
    last = int(re.search(r"^\s*WINDOW_LAST_DAY\s*=\s*(\d+)", text, re.M).group(1))
    return first * 86_400, (last + 1) * 86_400 - 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--task", required=True)
    parser.add_argument("--row", required=True, help="owner | meeting | first | last")
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)

    task_dir = REPO / "datasets" / args.dataset / "tasks" / args.task
    state = task_dir / "environment" / ".workbench" / "state" / "meetings.db"
    if not state.is_file():
        raise SystemExit(f"no served meetings at {state}")

    parts = [p.strip() for p in args.row.split("|")]
    if len(parts) != 4:
        raise SystemExit(
            f"expected 'owner | meeting | first | last', got {len(parts)} parts"
        )
    owner, group, first_held, last_held = parts

    oracle = json.loads((task_dir / "tests" / "oracle.json").read_text())
    cited = [
        row
        for row in oracle["blockers"]
        if row["owner"] == owner
        and row["meeting"] == group
        and row["first_raised"] == first_held
        and row["last_raised"] == last_held
    ]
    if not cited:
        raise SystemExit(f"the oracle holds no row {args.row!r}")

    sys.path.insert(0, str(REPO / "datasets" / args.dataset))
    rule = importlib.import_module("blocked_rule")
    # The net must CONTAIN the rule, or a turn the rule admits could be
    # missing from the evidence and the judges would never see it.
    for phrase in ("blocked on", "waiting on", "held up by", "stuck on", "can't move"):
        if not _NET.search(phrase):
            raise SystemExit(f"the net does not contain the rule's {phrase!r}")

    low, high = _window(task_dir / "solution" / "solve.py")
    connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    epoch = dt.datetime.fromisoformat(meta["epoch"])
    zone = ZoneInfo(meta.get("timezone", "America/New_York"))
    who = {
        name: person
        for person, name in connection.execute("SELECT person_id, name FROM people")
    }[owner]
    names = set(rule.roster(state.parent))

    lines = []
    for meeting_id, _pos, text, started in connection.execute(
        "SELECT u.meeting_id, u.position, u.text, m.started "
        "FROM utterances u JOIN meetings m ON m.meeting_id = u.meeting_id "
        "WHERE u.speaker = ? AND m.title = ? ORDER BY m.started, u.position",
        (who, group),
    ):
        if not (low <= started <= high) or not _NET.search(text or ""):
            continue
        day = (epoch + dt.timedelta(seconds=started)).astimezone(zone).date()
        admitted = rule.blocked_in(text, names)
        lines.append(
            f"[{day} {meeting_id}] "
            f"{'the key COUNTS this turn' if admitted else 'the key does NOT count it'}\n"
            f"    {text}"
        )
    connection.close()

    if not lines:
        raise SystemExit(
            f"no turn by {owner} in {group!r} mentions being stuck at all, and "
            "the oracle holds a row. That is a finding about the key"
        )

    row = cited[0]
    item = {
        "row": (
            f"owner {owner!r}, standing meeting {group!r}. The key says this "
            f"person first raised a blocker on {first_held}, last raised it on "
            f"{last_held}, and raised it in {row['raised_count']} meeting(s) of "
            "this series."
        ),
        "passage": (
            f"Every turn {owner} spoke in {group!r} that mentions being stuck "
            "in any form, in order. The marking says which ones the key counts; "
            "judge from the words, not from the marking.\n\n" + "\n\n".join(lines)
        ),
    }
    args.out.write_text(json.dumps([item], indent=2))
    counted = sum(1 for line in lines if "COUNTS" in line)
    print(f"  {args.out}: {len(lines)} turn(s) in the net, {counted} counted by the key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
