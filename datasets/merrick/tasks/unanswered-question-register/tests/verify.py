"""Second derivation of the unanswered-question register.

An independent verifier exists so the answer key is derived twice. Copying
the solver's arithmetic reproduces the solver's bugs and then certifies the
two agree, which is a check that cannot fail.

**The shape is deliberately different where the bug would be.** `solve.py`
computes one deadline date and compares each reply against it. A deadline
walk that counts wrong by one lands every Friday and Saturday question in
the wrong bucket, and a second walk written from the same mental model makes
the same mistake. So this file never computes a deadline: it enumerates the
**set of dates on which a reply would still count** and asks whether any
addressee sent on one of them. Membership in an explicit set has no
off-by-one to make.

The admitted rule and every threshold are read out of `instruction.md`, the
prose the agent is graded against, and `insists` fails loudly if the brief
stops saying what this arithmetic assumes. Zero shared code is not enough on
its own -- two files can hardcode the same misreading of a spec and never
disagree, which is how 20 of 27 brief mutations once went unnoticed on a
verifier that shared nothing.
"""

import datetime
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from brief_boundary import (  # noqa: E402
    check_reported,
    stated_boundary,
)
from brief_pins import unchanged  # noqa: E402

TASK = Path(__file__).resolve().parents[1]
BRIEF = (TASK / "instruction.md").read_text(encoding="utf-8")
_FLAT = " ".join(BRIEF.replace("**", "").split())


class BriefChanged(AssertionError):
    """The brief no longer says what this file's arithmetic assumes."""


def insists(condition: object, what: str) -> None:
    if not condition:
        raise BriefChanged(
            f"instruction.md no longer states: {what}. The verifier's "
            "arithmetic assumes it. Re-read the brief and this file together "
            "-- do not relax the assertion."
        )


def _grace_from_brief() -> int:
    """The response window, in working days, taken from the brief's words."""

    words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
        "six": 6,
        "seven": 7,
        "eight": 8,
        "nine": 9,
        "ten": 10,
    }
    found = re.search(r"within \*{0,2}(\w+) working days\*{0,2}", BRIEF)
    insists(found, "a response window phrased as 'within N working days'")
    token = found.group(1).lower()
    value = words.get(token, int(token) if token.isdigit() else None)
    insists(value, f"a readable number of working days (saw {token!r})")
    return value


GRACE = _grace_from_brief()

insists(GRACE == 3, f"a three-working-day response window (brief says {GRACE})")
insists(
    "day the question was sent is day zero" in _FLAT,
    "the day the question was sent is day zero",
)
insists(
    "Friday the 9th, Monday the 12th and Tuesday the 13th" in _FLAT,
    "the worked weekend example, which fixes how working days are counted. "
    "The first version said a Monday question replied to on the following "
    "Tuesday was 'two days late' -- 6 working days out, so three late, and "
    "ambiguous besides. A worked example that does not work is worse than "
    "none in a task whose whole difficulty is this arithmetic",
)
insists(
    "People in Cc are not asked" in _FLAT,
    "Cc recipients are not addressees",
)
insists(
    "reply from someone who was only in Cc does not answer it" in _FLAT,
    "a Cc reply does not close a question",
)
insists(
    "Neither does a reply from the asker" in _FLAT,
    "the asker's own later message does not close their question",
)
insists(
    "reply that arrives late does not answer it" in _FLAT,
    "a reply after the window still leaves the question a row",
)
insists(
    "in the same thread" in _FLAT,
    "the reply must be in the same thread",
)
insists(
    "body contains a question mark" in _FLAT,
    "the admission test is a literal question mark, not detected intent",
)
insists(
    "addressees` is sorted alphabetically" in _FLAT,
    "the addressee list is sorted alphabetically",
)
insists("mail only" in _FLAT, "chat is out of scope")
insists("not by UTC" in _FLAT, "dates are read in the firm's own time zone")


# Every `insists` above is a substring test, so none can see an exception
# ADDED to a rule -- the brief could gain "...unless the sender copied
# themselves" and each pinned sentence would still be present. An audit
# measured that blind spot at 17-of-18 and 12-of-16 unnoticed mutations on
# this dataset's older verifiers.
#
# The digest closes it: any edit to the rule section breaks this, including
# a pure addition. When it fires, re-read the section against the code
# below and confirm the second derivation still implements it before
# re-pinning -- do not paste the new value in to make it pass.
unchanged(BRIEF, "## What makes a row", "c19f2700dfe31f37")


def counting_dates(sent: datetime.date, working_days: int = GRACE) -> set:
    """Every date on which a reply would still be in time.

    The set includes the day the question was sent (day zero) and the next
    `working_days` weekdays. Weekend days in between are present too: a
    Saturday reply to a Friday question is in time, it simply does not
    consume one of the working days. Building the set makes that explicit
    rather than leaving it to a comparison against a single boundary.
    """

    allowed = {sent}
    counted, cursor = 0, sent
    while counted < working_days:
        cursor += datetime.timedelta(days=1)
        allowed.add(cursor)
        if cursor.weekday() < 5:
            counted += 1
    return allowed


def recompute(state: Path, window_days: int) -> dict:
    mail = sqlite3.connect(f"file:{state / 'gmail.db'}?mode=ro", uri=True)
    started = datetime.datetime.fromisoformat(
        dict(mail.execute("SELECT key, value FROM meta"))["epoch"]
    )
    horizon = window_days * 86_400
    named = dict(mail.execute("SELECT person_id, name FROM people"))

    def stamp(seconds: int) -> datetime.date:
        return (started + datetime.timedelta(seconds=seconds)).date()

    asked_of: dict[str, set] = {}
    for note, who, slot in mail.execute(
        "SELECT message_id, person_id, kind FROM recipients"
    ):
        if slot == "to":
            asked_of.setdefault(note, set()).add(who)

    # Who sent something in each thread, and on which dates. Indexing this way
    # means answering a question is a set lookup rather than a scan with a
    # comparison in it.
    spoke_on: dict[tuple, set] = {}
    body_of, subject_of, sender_of, thread_of, when_of = {}, {}, {}, {}, {}
    for note, chain, who, seconds, line, text in mail.execute(
        "SELECT message_id, thread_id, sender, time, subject, body FROM messages"
    ):
        spoke_on.setdefault((chain, who), set()).add((stamp(seconds), seconds))
        body_of[note], subject_of[note] = text or "", line
        sender_of[note], thread_of[note], when_of[note] = who, chain, seconds

    out, read = [], 0
    for note, text in body_of.items():
        if when_of[note] >= horizon:
            continue
        to = asked_of.get(note)
        if not to or "?" not in text:
            continue
        read += 1
        in_time = counting_dates(stamp(when_of[note]))
        closed = any(
            on in in_time and at > when_of[note]
            for who in to
            for on, at in spoke_on.get((thread_of[note], who), ())
        )
        if closed:
            continue
        out.append(
            {
                "message_ref": note,
                "thread_ref": thread_of[note],
                "asker": named.get(sender_of[note], sender_of[note]),
                "asked_date": stamp(when_of[note]).isoformat(),
                "subject": subject_of[note],
                "addressees": sorted(named.get(p, p) for p in to),
            }
        )
    out.sort(key=lambda r: r["message_ref"])
    return {"questions_read": read, "unanswered": out}


def boundary_agrees(oracle: dict) -> None:
    """The brief's stated boundary must be the one the oracle was built on.

    Nothing compared these. The verifier took its window from `argv`, the
    build supplied that from the solver's own constant, and the brief's
    boundary sentence -- the thing the agent actually reads and windows on --
    was never in the loop. A brief saying one date while the oracle was cut
    on another grades every row against a window nobody was told about, and
    every row-level comparison stays green because both derivations share the
    integer.

    Skipped while the task is staged: the boundary is still a «MEASURE»
    placeholder, so there is no date to disagree with. It arms itself the
    moment one is written.
    """

    if "«MEASURE" in BRIEF:
        return
    reported = str(oracle.get("window_end", ""))
    try:
        stated = datetime.date.fromisoformat(reported)
    except ValueError:
        raise BriefChanged(
            f"the oracle's window_end is {reported!r}, which is not a date"
        ) from None
    stated_boundary(BRIEF, stated, "## The window")
    check_reported(oracle, stated)


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: verify.py <state-dir> <window-days> <oracle.json>")
        return 2
    mine = recompute(Path(sys.argv[1]), int(sys.argv[2]))
    theirs = json.loads(Path(sys.argv[3]).read_text(encoding="utf-8"))
    boundary_agrees(theirs)
    ok = True
    if mine["questions_read"] != theirs.get("questions_read"):
        print(
            f"questions_read: {mine['questions_read']} "
            f"vs {theirs.get('questions_read')}"
        )
        ok = False
    left = {r["message_ref"]: r for r in mine["unanswered"]}
    right = {r["message_ref"]: r for r in theirs.get("unanswered", [])}
    for ref in sorted(set(left) | set(right)):
        if ref not in right:
            print(f"only the verifier admits {ref}")
            ok = False
        elif ref not in left:
            print(f"only the solver admits {ref}")
            ok = False
        elif left[ref] != right[ref]:
            print(f"{ref} differs: {left[ref]} vs {right[ref]}")
            ok = False
    print(
        f"{'agree' if ok else 'DISAGREE'}: "
        f"{len(left)} verifier rows, {len(right)} solver rows"
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
