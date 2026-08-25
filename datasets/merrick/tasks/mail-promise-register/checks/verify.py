"""Second derivation of `mail-promise-register`, and the brief's pins.

The rule for "is this a promise, and when is it due" comes from
`promise_rule_check`, which walks words where the solver's `promise_rule`
walks characters. `build_tasks` vendors both. This file carries only what
is about THIS corpus: the window, the supersession unit, and the phrases in
the brief that the arithmetic below rests on.

Run by `build_tasks` after the solver, against the same bundle. A
disagreement is a finding about one of the two, never a bug to be silenced
by making this file agree.
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

from brief_pins import RuleChanged, unchanged  # noqa: E402
from promise_rule_check import _committed_in, _resolve  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
BRIEF = Path(__file__).resolve().parents[1] / "instruction.md"
ORACLE = Path(__file__).resolve().parents[1] / "tests" / "oracle.json"

# The rule sections this file implements, pinned by digest. A substring pin
# catches a rule being removed or reworded and is blind by construction to
# one being ADDED -- a brief can gain "...unless the sender copied
# themselves" and every quoted sentence still appears. The digest closes
# that: any edit to a rule section at all breaks this, including a pure
# addition. When it fires, re-read the section against the code here and
# confirm the derivation still implements it before re-pinning.
PINNED: dict[str, str] = {
    "## What counts as a promise": "6c2be58322a32de0",
    "## Turning what was said into a date": "c8f8a8253e49bbef",
    "## Which promise is the live one": "bdd62ac3bcd3ed3d",
}

# The window, as dates. Restated rather than derived from the solver's
# integer: taking the same number from the same place would make this a
# second copy rather than a second derivation, and a window off by a day
# would be invisible to both.
WINDOW_FIRST_DATE = "2026-01-05"
WINDOW_LAST_DATE = "2026-03-06"

# Every phrase the arithmetic below assumes is still in the brief.
_STATED: dict[str, tuple[str, ...]] = {
    "## What counts as a promise": (
        "in the same clause",
        "`i'll` or",
        "day comes after the promise",
        "attached to the promise",
        "nobody else's clause stands between the promise and the day",
        "no negation stands between the promise and the day",
    ),
    "## Which promise is the live one": (
        # The supersession unit, which is the whole design. Per PERSON and
        # not per thread: measured at 2% of rows changing inside a thread
        # against 50% across a person's mail, because this firm opens a new
        # thread rather than re-promising in an old one.
        "one live promise per person",
        "the most recent",
        "mail only",
    ),
}


def insists(where: str, chunk: str, phrases: tuple[str, ...]) -> list[str]:
    flattened = " ".join(chunk.split()).casefold()
    return [
        f"{where}: the brief no longer says {phrase!r}, which this file's "
        "derivation assumes"
        for phrase in phrases
        if phrase.casefold() not in flattened
    ]


def section(brief: str, heading: str) -> str:
    start = brief.index(heading)
    end = brief.find("\n## ", start + 1)
    return brief[start : end if end > 0 else len(brief)]


def _zone(connection: sqlite3.Connection) -> tuple[datetime.datetime, ZoneInfo]:
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    zone = ZoneInfo(meta.get("timezone", "America/New_York"))
    return datetime.datetime.fromisoformat(meta["epoch"]), zone


def main() -> int:
    problems: list[str] = []
    brief = BRIEF.read_text(encoding="utf-8")
    for heading, phrases in _STATED.items():
        if heading not in brief:
            problems.append(f"the brief has no section {heading!r}")
            continue
        problems.extend(insists(heading, section(brief, heading), phrases))
    for heading, expected in PINNED.items():
        if not expected:
            continue
        try:
            unchanged(brief, heading, expected)
        except RuleChanged as changed:
            problems.append(str(changed))
    if problems:
        return _report(problems)

    gmail = sqlite3.connect(f"file:{STATE / 'gmail.db'}?mode=ro", uri=True)
    epoch, zone = _zone(gmail)
    first = datetime.date.fromisoformat(WINDOW_FIRST_DATE)
    last = datetime.date.fromisoformat(WINDOW_LAST_DATE)
    people = dict(gmail.execute("SELECT person_id, name FROM people"))

    promised: dict[str, list[tuple]] = defaultdict(list)
    read = 0
    for message_id, sender, when, subject, body in gmail.execute(
        "SELECT message_id, sender, time, subject, body FROM messages"
    ):
        said = (epoch + datetime.timedelta(seconds=when)).astimezone(zone).date()
        if not (first <= said <= last):
            continue
        read += 1
        token = _committed_in(body or "")
        if token is None:
            continue
        promised[sender].append((said, _resolve(said, token), message_id, subject))

    rows = []
    superseded = 0
    for sender, made in promised.items():
        superseded += len({due for _, due, _, _ in made}) - 1
        said, due, message_id, subject = max(made)
        rows.append(
            {
                "owner": people.get(sender, sender),
                "due": due.isoformat(),
                "message_ref": message_id,
                "said_on": said.isoformat(),
                "subject": subject,
            }
        )
    rows.sort(key=lambda r: (r["owner"], r["due"]))

    oracle = json.loads(ORACLE.read_text(encoding="utf-8"))
    mine = {
        "window_end": last.isoformat(),
        "messages_read": read,
        "superseded_count": superseded,
        "owed": rows,
    }
    for field in ("window_end", "messages_read", "superseded_count"):
        if oracle.get(field) != mine[field]:
            problems.append(
                f"{field}: the oracle says {oracle.get(field)!r}, this "
                f"derivation says {mine[field]!r}"
            )
    theirs = {(r["owner"], r["due"]): r for r in oracle.get("owed", [])}
    ours = {(r["owner"], r["due"]): r for r in mine["owed"]}
    for key in sorted(set(theirs) | set(ours)):
        if key not in theirs:
            problems.append(f"this derivation has a row the oracle does not: {key}")
        elif key not in ours:
            problems.append(f"the oracle has a row this derivation does not: {key}")
        else:
            for field in ("message_ref", "said_on", "subject"):
                if theirs[key].get(field) != ours[key].get(field):
                    problems.append(
                        f"{key} {field}: oracle {theirs[key].get(field)!r} vs "
                        f"{ours[key].get(field)!r}"
                    )
    if problems:
        return _report(problems)
    print(f"mail-promise-register: second derivation agrees ({len(rows)} rows)")
    return 0


def _report(problems: list[str]) -> int:
    print("mail-promise-register: the independent verifier disagrees.")
    for problem in problems:
        print(f"  {problem}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
