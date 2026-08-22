"""An independent derivation of the same answer.

    WORKBENCH_STATE=out/merrick/bundle/state uv run python \
        datasets/merrick/tasks/live-commitment-register/checks/verify.py

Everything below is transcribed from `instruction.md` — the prose the agent
is graded against — and nothing from `solution/solve.py`. Copying the
solver's expression reproduces its bug and then certifies that the two
agree; two published scores in this tree were the answer key rather than a
measurement, certified exactly that way.

Where more than one computation is defensible, this uses the one the solver
did not:

**The window is a calendar date here, not a day offset.** The instruction
names a Monday and a Friday; the solver multiplies a zero-based day index
by 86,400. Their agreement would be no evidence — a shifted boundary makes
every row wrong together while every row-level check stays green — so this
converts each meeting's `started` to a wall-clock date in the firm's own
zone and compares dates.

**The deadline is tokenised here, not matched by regex.** The solver runs
each admitted form as a pattern and takes the first that hits. This splits
the turn on non-word characters and asks whether the form's own tokens
appear in order. A hyphenated or punctuated writing yields the same answer
either way; a longer word containing the letters yields neither.

**The speaker's name comes from a different surface.** The solver reads
`people` out of `meetings.db`. This reads it out of `clio.db` — the surface
that serves the firm's timekeepers — and keys on the person id the
transcript records, so a directory that disagrees between surfaces is a
finding rather than a silent agreement.

**Supersession is resolved by maximum, not by sort.** The solver sorts the
statements and takes the last. This groups them and selects the one whose
meeting start is greatest, breaking a tie on the later position — the same
rule reached from the other end, so an ordering bug shows up as a
disagreement instead of being shared.

**The counts are recomputed from the rows this file derived**, never read
back from the answer, so a report that tallies its own wrong register
correctly still fails here.

Every `«MEASURE»` is a value this world has not finished recording. The
guard is a call that raises rather than a placeholder that is a syntax
error: the file compiles, the schema gates can read it, and running it
before the measurement lands fails loudly with the question outstanding.
"""
# ruff: noqa: E501
# Long lines are the «MEASURE» questions, written out in full.

import datetime
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from brief_pins import RuleChanged, unchanged  # noqa: E402
from pending import measure  # noqa: E402

STATE = Path(os.environ["WORKBENCH_STATE"])
BRIEF = Path(__file__).resolve().parents[1] / "instruction.md"
ORACLE = Path(__file__).resolve().parents[1] / "tests" / "oracle.json"

# The rule sections this file implements, pinned by digest. A substring
# pin catches a rule being removed or reworded and is blind by construction
# to one being *added*: a brief can gain "...unless the meeting was
# cancelled" and every quoted sentence still appears. An audit measured the
# cost across this dataset's older verifiers — 17 of 18 and 12 of 16 brief
# mutations went unnoticed, including full inversions of a rule.
#
# Deliberately coarse. Rewording a section without changing its meaning
# fails this, and the right response is to re-read this file against the
# new wording and re-pin, not to loosen the pin.
#
# «MEASURE: the digests, once the brief is filled. `brief_pins.digest(brief,
# heading)` prints them. Pin every section that states a rule this file
# implements, and no section that does not — a pin on prose nobody derives
# from is a tripwire that fires for nothing.»
PINNED: dict[str, str] = {
    "## What counts as a commitment": measure("digest of the commitment rule section"),
    "## Which one is live": measure("digest of the supersession rule section"),
}

# The firm's own zone, read from the served meta table rather than named
# here — an oracle that computes a moment differently from the surface it
# grades is a defect this dataset has shipped twice.
#
# «MEASURE: confirm the epoch and zone the served surfaces carry, and note
# that a fixed-offset epoch and a zone that observes daylight saving part
# company at the transition. If the window reaches past one, the two
# derivations disagree near midnight and THAT DISAGREEMENT IS THE FINDING,
# not a bug in this file.»
WINDOW_FIRST_DATE = measure("the window's first day as an ISO calendar date")
WINDOW_LAST_DATE = measure("the window's last day as an ISO calendar date")

# «MEASURE: the admitted deadline forms and their normalised tokens, read
# out of the brief's own table rather than restated here once the table
# exists. Until then this is the question. Include the relative forms —
# a weekday-only rule was measured dead on this world: 14% of turns name a
# weekday against 41% naming a relative deadline, and the weekday-only
# register held six rows with no supersession at all.»
ADMITTED = measure("the brief's deadline table, as (form, normalised token) pairs")

# «MEASURE: the owner-shaped phrasings, likewise from the brief.»
OWNER_FORMS = measure("the brief's owner-phrase list")

# A register below this is not a task, it is a coin flip. Twelve is this
# dataset's floor and it is a policy about the task, not a count of the
# corpus — the corpus supplies the number that gets compared to it.
ROW_FLOOR = 12

# Below this share of rows superseded to a *different* deadline, a reader
# who takes the first answer is never wrong and the task grades nothing it
# was built to grade.
SUPERSESSION_FLOOR = 0.15


def fail(message: str) -> str:
    return message


def _zone(connection: sqlite3.Connection) -> tuple[datetime.datetime, ZoneInfo]:
    """The epoch and zone the served surfaces carry, from the meta table."""

    row = connection.execute("SELECT key, value FROM meta").fetchall()
    meta = {k: v for k, v in row}
    epoch = datetime.datetime.fromisoformat(meta["epoch"])
    return epoch, ZoneInfo(meta.get("timezone", "America/New_York"))


def _date_of(epoch: datetime.datetime, zone: ZoneInfo, seconds: int) -> datetime.date:
    """A meeting's calendar date in the firm's own zone.

    The solver never computes a date at all; it works in offsets. This is
    the whole point of the divergence — a window boundary that has slipped
    by a day is invisible to any check that uses the same offsets on both
    sides.
    """

    return (epoch + datetime.timedelta(seconds=seconds)).astimezone(zone).date()


def _tokens(text: str) -> list[str]:
    """The turn as words, split the way the brief defines a word boundary."""

    return [token.casefold() for token in re.split(r"[^\w]+", text or "") if token]


def _names_form(tokens: list[str], form: str) -> bool:
    """Whether `form`'s own tokens appear, in order, as whole words.

    Not a regex. A form of one word is a membership test; a form of
    several — "end of week" — is a contiguous-subsequence test, which is
    what "the words around it do not remove it" means when the form itself
    is a phrase.
    """

    wanted = _tokens(form)
    if not wanted:
        return False
    for start in range(len(tokens) - len(wanted) + 1):
        if tokens[start : start + len(wanted)] == wanted:
            return True
    return False


def _deadline(tokens: list[str]) -> str | None:
    for form, token in ADMITTED:
        if _names_form(tokens, form):
            return token
    return None


def main() -> int:
    problems: list[str] = []

    brief = BRIEF.read_text(encoding="utf-8")
    for heading, expected in PINNED.items():
        try:
            unchanged(brief, heading, expected)
        except RuleChanged as changed:
            problems.append(fail(str(changed)))
    if problems:
        return _report(problems)

    meetings = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    clio = sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True)
    epoch, zone = _zone(meetings)
    first = datetime.date.fromisoformat(WINDOW_FIRST_DATE)
    last = datetime.date.fromisoformat(WINDOW_LAST_DATE)

    # Names from clio, not from the meetings surface the solver reads.
    people = {
        person_id: name
        for person_id, name in clio.execute("SELECT person_id, name FROM people")
    }
    # «MEASURE: the matter handles, derived here by a different route from
    # the solver's. The solver builds them from clio's matter descriptions;
    # this should reach the same set another way — the brief states how a
    # matter is named, and this file implements the brief.»
    handles: dict[str, str] = measure(
        "the matter handles, derived independently of the solver"
    )

    in_window = {}
    for meeting_id, started in meetings.execute(
        "SELECT meeting_id, started FROM meetings"
    ):
        if first <= _date_of(epoch, zone, started) <= last:
            in_window[meeting_id] = started

    statements: dict[tuple[str, str], list] = defaultdict(list)
    turns_read = 0
    for meeting_id, position, speaker, text in meetings.execute(
        "SELECT meeting_id, position, speaker, text FROM utterances"
    ):
        if meeting_id not in in_window:
            continue
        turns_read += 1
        tokens = _tokens(text)
        if not any(_names_form(tokens, form) for form in OWNER_FORMS):
            continue
        deadline = _deadline(tokens)
        if deadline is None:
            continue
        for handle, display in handles.items():
            if _names_form(tokens, handle):
                statements[(speaker, display)].append(
                    (in_window[meeting_id], position, meeting_id, deadline)
                )

    # Resolved by maximum, not by sorting and taking the last.
    rows = []
    superseded = 0
    for (speaker, matter), made in statements.items():
        superseded += len(made) - 1
        started, _position, meeting_id, deadline = max(made, key=lambda s: (s[0], s[1]))
        rows.append(
            {
                "matter": matter,
                "owner": people.get(speaker, speaker),
                "day": deadline,
                "meeting_id": meeting_id,
                "said_at": (epoch + datetime.timedelta(seconds=started)).isoformat(),
            }
        )
    rows.sort(key=lambda row: (row["matter"], row["owner"]))

    truth = json.loads(ORACLE.read_text(encoding="utf-8"))

    def check(field: str, mine) -> None:
        if truth.get(field) != mine:
            problems.append(
                fail(f"{field}: oracle {truth.get(field)!r} != derived {mine!r}")
            )

    check("meetings_read", len(in_window))
    check("turns_read", turns_read)
    check("superseded_count", superseded)
    check("distinct_owners", len({row["owner"] for row in rows}))
    check("matters_with_a_commitment", len({row["matter"] for row in rows}))
    check("live", rows)

    # Floors no per-row criterion can see.
    if len(rows) < ROW_FLOOR:
        problems.append(fail(f"row floor: {len(rows)} rows, fewer than {ROW_FLOOR}"))

    keyed = {(row["matter"], row["owner"], row["day"]) for row in rows}
    if len(keyed) != len(rows):
        problems.append(
            fail(
                f"key collapse: {len(rows)} rows key to {len(keyed)} — the ceiling "
                "is below 1.0 and row F1 will not show it, because both sides "
                "dedupe identically"
            )
        )
    owned = {(row["matter"], row["owner"]) for row in rows}
    if len(owned) != len(rows):
        problems.append(
            fail(
                f"two live commitments for one person on one matter: {len(rows)} "
                f"rows over {len(owned)} pairs. The brief admits one; the later "
                "statement replaced the earlier."
            )
        )

    # The mechanism the task exists to grade. A register nothing supersedes
    # makes a reader who takes the first answer always right, and the task
    # scores comprehension it never tested.
    changed = sum(
        1
        for made in statements.values()
        if len(made) > 1
        and min(made, key=lambda s: (s[0], s[1]))[3]
        != max(made, key=lambda s: (s[0], s[1]))[3]
    )
    share = changed / len(rows) if rows else 0.0
    if share < SUPERSESSION_FLOOR:
        problems.append(
            fail(
                f"supersession: {changed} of {len(rows)} rows carry a deadline "
                f"that changed ({share:.0%}), under the {SUPERSESSION_FLOOR:.0%} "
                "floor. A weekday-only rule read 0% on this engine; check the "
                "admitted forms before the window."
            )
        )

    for field in ("day", "owner", "matter"):
        distinct = {row[field] for row in rows}
        if rows and len(distinct) < 2:
            problems.append(
                fail(
                    f"constant field: every row has {field}={distinct.pop()!r}, so "
                    "an agent that never looks scores full marks on it"
                )
            )

    if problems:
        return _report(problems)
    print(
        f"verify: {len(rows)} live commitments over {len(in_window)} meetings "
        f"agree with the oracle, derived from instruction.md by a second route."
    )
    return 0


def _report(problems: list[str]) -> int:
    for problem in problems:
        print(f"  MISMATCH  {problem}")
    print(f"\n{len(problems)} disagreement(s) between instruction.md and the oracle.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
