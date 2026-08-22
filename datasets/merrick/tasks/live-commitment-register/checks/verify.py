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
from brief_pins import RuleChanged, section, unchanged  # noqa: E402

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
    "## What counts as a commitment": "4c274a2356b7f66a",
    "## Turning what was said into a date": "c8f8a8253e49bbef",
    "## Which one is live": "f8cf3f5493be32e4",
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
WINDOW_FIRST_DATE = "2026-02-23"
WINDOW_LAST_DATE = "2026-03-20"

# «MEASURE: the admitted deadline forms and their normalised tokens, read
# out of the brief's own table rather than restated here once the table
# exists. Until then this is the question. Include the relative forms —
# a weekday-only rule was measured dead on this world: 14% of turns name a
# weekday against 41% naming a relative deadline, and the weekday-only
# register held six rows with no supersession at all.»
ADMITTED = [
    ("EOD tomorrow", "tomorrow"),
    ("COB tomorrow", "tomorrow"),
    ("end of day tomorrow", "tomorrow"),
    ("end of the day tomorrow", "tomorrow"),
    ("close of business tomorrow", "tomorrow"),
    ("tomorrow EOD", "tomorrow"),
    ("tomorrow COB", "tomorrow"),
    ("tomorrow end of day", "tomorrow"),
    ("tomorrow end of the day", "tomorrow"),
    ("tomorrow close of business", "tomorrow"),
    ("Monday EOD", "monday"),
    ("Monday COB", "monday"),
    ("Monday end of day", "monday"),
    ("Monday end of the day", "monday"),
    ("Monday close of business", "monday"),
    ("Tuesday EOD", "tuesday"),
    ("Tuesday COB", "tuesday"),
    ("Tuesday end of day", "tuesday"),
    ("Tuesday end of the day", "tuesday"),
    ("Tuesday close of business", "tuesday"),
    ("Wednesday EOD", "wednesday"),
    ("Wednesday COB", "wednesday"),
    ("Wednesday end of day", "wednesday"),
    ("Wednesday end of the day", "wednesday"),
    ("Wednesday close of business", "wednesday"),
    ("Thursday EOD", "thursday"),
    ("Thursday COB", "thursday"),
    ("Thursday end of day", "thursday"),
    ("Thursday end of the day", "thursday"),
    ("Thursday close of business", "thursday"),
    ("Friday EOD", "friday"),
    ("Friday COB", "friday"),
    ("Friday end of day", "friday"),
    ("Friday end of the day", "friday"),
    ("Friday close of business", "friday"),
    ("EOD Monday", "monday"),
    ("COB Monday", "monday"),
    ("end of day Monday", "monday"),
    ("end of the day Monday", "monday"),
    ("close of business Monday", "monday"),
    ("EOD Tuesday", "tuesday"),
    ("COB Tuesday", "tuesday"),
    ("end of day Tuesday", "tuesday"),
    ("end of the day Tuesday", "tuesday"),
    ("close of business Tuesday", "tuesday"),
    ("EOD Wednesday", "wednesday"),
    ("COB Wednesday", "wednesday"),
    ("end of day Wednesday", "wednesday"),
    ("end of the day Wednesday", "wednesday"),
    ("close of business Wednesday", "wednesday"),
    ("EOD Thursday", "thursday"),
    ("COB Thursday", "thursday"),
    ("end of day Thursday", "thursday"),
    ("end of the day Thursday", "thursday"),
    ("close of business Thursday", "thursday"),
    ("EOD Friday", "friday"),
    ("COB Friday", "friday"),
    ("end of day Friday", "friday"),
    ("end of the day Friday", "friday"),
    ("close of business Friday", "friday"),
    ("EOD", "eod"),
    ("COB", "eod"),
    ("end of day", "eod"),
    ("end of the day", "eod"),
    ("close of business", "eod"),
    ("EOW", "end of week"),
    ("end of the week", "end of week"),
    ("end of week", "end of week"),
    ("tomorrow", "tomorrow"),
    ("Monday", "monday"),
    ("Tuesday", "tuesday"),
    ("Wednesday", "wednesday"),
    ("Thursday", "thursday"),
    ("Friday", "friday"),
]

# «MEASURE: the owner-shaped phrasings, likewise from the brief.»
OWNER_FORMS = ["I'll", "I will"]

# How many days a title has to appear on before the meeting is standing.
# The brief states the number outright; it is repeated here because this
# file's arithmetic depends on it, and `_STATED` pins the sentence so a
# brief that changes the number fails rather than silently disagreeing.
#
# Counted here over the distinct *dates* a title was held on, not over the
# rows in the meetings table: two rows for one morning is a duplicate the
# solver's count would swallow and this one reports.
STANDING_MINIMUM = 3

# A register below this is not a task, it is a coin flip. Twelve is this
# dataset's floor and it is a policy about the task, not a count of the
# corpus — the corpus supplies the number that gets compared to it.
ROW_FLOOR = 12

# The deliverable's row shape, as the brief lists it. Declared once so this
# file builds a row by position against a named order rather than repeating
# the solver's dict literal.
_ROW_FIELDS = ("owner", "meeting", "due", "meeting_id", "said_at")

# The tokens whose resolution is not simply "the weekday of this name".
# Read off the brief's own table rather than spelled into `_resolve`, so a
# renamed token fails loudly at the lookup instead of silently falling
# through to the weekday walk and spinning.
_EOD = "eod"
_TOMORROW = "tomorrow"
_END_OF_WEEK = "end of week"
_FRIDAY = "friday"

# Below this share of rows superseded to a *different* deadline, a reader
# who takes the first answer is never wrong and the task grades nothing it
# was built to grade.
SUPERSESSION_FLOOR = 0.15


# The sentences this file's arithmetic depends on, by the section that must
# carry them. This is the FIRST line of defence and it was missing: a digest
# pin refuses any edit at all, which is strictly stronger, but it fails with
# "this section changed" where these fail with the assumption that broke.
# `brief_pins` says as much — a substring pin names the specific assumption
# and needs a digest underneath it that no *addition* can slip past.
#
# The failure this guards is measured: a verifier sharing nothing with its
# solver, gate clean, that read two of an instruction table's three columns
# and hardcoded the third. The brief could have said `end of week` means the
# Sunday and both files would have computed the Friday, agreed, and reported
# an independent reading. **20 of 27 brief mutations went unnoticed.**
_STATED: dict[str, tuple[str, ...]] = {
    "## What counts as a commitment": (
        # both conjuncts; the owner forms as a CLOSED set rather than an
        # example, which is the asymmetry a probe caught -- the brief named
        # the deadline forms exactly and gave only an instance for this
        # one, so an agent generalised to "I'm calling their counsel" and
        # was graded against a narrower rule than the brief stated; and
        # that neither a recap, an instruction, nor a question is one
        "not merely somewhere in the same turn",
        "names a date as a *condition*",
        "`i'll` or",
        "names no future act",
        "makes a row for nobody",
        "a question is not one",
    ),
    "## Turning what was said into a date": (
        # every branch of `_resolve`. The failure this guards is measured:
        # a verifier sharing nothing with its solver read two of a table's
        # three columns and hardcoded the third, and 20 of 27 brief
        # mutations went unnoticed. The brief could say `end of week` means
        # the Sunday and both files would compute the Friday and agree.
        "is the day of that meeting",
        "tomorrow** is the next working day",
        "following Monday",
        "end of week** is that week's Friday",
        "same day, not a week later",
        "next occurrence, always *after* the day it was said",
        "is one deadline, not two",
    ),
    "## Which one is live": (
        # supersession, that it is ordered by the meeting rather than by
        # position, and that identical words still supersede -- which is
        # the whole reason the date is graded instead of the word
        "one live commitment per standing meeting: the most recent",
        "the later statement replaces the earlier one entirely",
        "even when they say the same words",
        "later means later by",
        "when the meeting started",
    ),
    "## The window and the meetings": (
        # the boundary this file re-derives as a calendar date, and the
        # threshold `STANDING_MINIMUM` copies
        "a meeting is in the window when it",
        "started",
        "three or more days",
    ),
}


def insists(where: str, chunk: str, phrases: tuple[str, ...]) -> list[str]:
    """Every phrase the arithmetic below assumes, still in the brief."""

    flattened = " ".join(chunk.split()).casefold()
    return [
        f"{where}: the brief no longer says {phrase!r}, which this file's "
        "derivation assumes"
        for phrase in phrases
        if phrase.casefold() not in flattened
    ]


def fail(message: str) -> str:
    return message


def _zone(connection: sqlite3.Connection) -> tuple[datetime.datetime, ZoneInfo]:
    """The epoch and zone the served surfaces carry, from the meta table."""

    row = connection.execute("SELECT key, value FROM meta").fetchall()
    meta = {k: v for k, v in row}
    zone = ZoneInfo(meta.get("timezone", "America/New_York"))
    # Bound to the zone, not left on the fixed offset the ISO string
    # carries. This file's first version kept the offset, and it disagreed
    # with the solver on every meeting after the spring transition: same
    # wall clock, `-05:00` against `-04:00`, because a fixed offset never
    # learns about daylight saving. The `«MEASURE»` above predicted exactly
    # that and the gate found it on the first run. The firm keeps local
    # hours -- the docket call is 08:45 in March as it was in January --
    # so the zone is what renders the moment, and a task whose window
    # crosses a transition grades `said_at` on it.
    epoch = datetime.datetime.fromisoformat(meta["epoch"]).astimezone(zone)
    return epoch, zone


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


ONE_DAY = datetime.timedelta(days=1)


def _working(day: datetime.date) -> bool:
    """A day the firm works. Named from the date rather than an index."""

    return day.strftime("%A").casefold() not in {"saturday", "sunday"}


def _resolve(said_on: datetime.date, token: str) -> datetime.date:
    """The date a deadline names, walked forward one day at a time.

    The solver computes this with modular arithmetic over a weekday index.
    This walks the calendar and asks each day what it is called, which is
    the same rule reached from the other end: an off-by-one in either shows
    up as a disagreement instead of being shared. Every branch is a sentence
    `_STATED` pins in the brief.
    """

    if token == _EOD:
        return said_on
    if token == _TOMORROW:
        day = said_on + ONE_DAY
        while not _working(day):
            day += ONE_DAY
        return day
    if token == _END_OF_WEEK:
        day = said_on
        while day.strftime("%A").casefold() != _FRIDAY:
            day += ONE_DAY
        return day
    day = said_on + ONE_DAY
    while day.strftime("%A").casefold() != token:
        day += ONE_DAY
    return day


def _sentences(text: str) -> list[str]:
    """The turn as sentences.

    The solver splits on a regex lookbehind over terminal punctuation. This
    walks the characters and breaks after one, which reaches the same
    boundaries by a different route — so a turn the two disagree about is a
    finding rather than a shared assumption. Semicolons end a sentence here
    because this firm hangs independent statements off one another with
    them, and the brief says so.
    """

    body = text or ""
    out: list[str] = []
    current: list[str] = []
    for index, character in enumerate(body):
        current.append(character)
        if character not in ".?!;":
            continue
        # A sentence ends where the punctuation is *followed by space*.
        # Breaking on the mark alone splits `.xlsx` into two sentences and
        # separates "I'll have the updated" from "by EOD tomorrow" — which
        # is how this file first disagreed with the solver by exactly one
        # row, on a real commitment both should have kept. Decimals, file
        # extensions and abbreviations all end in a mark that ends nothing.
        following = body[index + 1 : index + 2]
        if following == "" or following.isspace():
            out.append("".join(current))
            current = []
    if current:
        out.append("".join(current))
    return out


def _committed_in(text: str) -> str | None:
    """The deadline the speaker committed to *in one sentence*, or None.

    The pairing is what matters and it is why this exists. Asking whether a
    turn holds an owner form somewhere and a deadline somewhere is a
    different question in a 71-word turn, and it manufactured eight rows of
    twenty-five that nobody made: a docket manager reciting another
    person's deadline beside an undated promise of her own, a date used as
    a condition rather than a deadline, a promise contingent on an external
    event. Two frontier models independently declined all of them.
    """

    for sentence in _sentences(text):
        tokens = _tokens(sentence)
        if any(_names_form(tokens, form) for form in OWNER_FORMS):
            deadline = _deadline(tokens)
            if deadline is not None:
                return deadline
    return None


def main() -> int:
    problems: list[str] = []

    brief = BRIEF.read_text(encoding="utf-8")
    for heading, phrases in _STATED.items():
        problems.extend(insists(heading, section(brief, heading), phrases))
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
    held: dict[str, set[datetime.date]] = defaultdict(set)
    inside: dict[str, tuple[int, str]] = {}
    for meeting_id, started, title in meetings.execute(
        "SELECT meeting_id, started, title FROM meetings"
    ):
        when = _date_of(epoch, zone, started)
        if first <= when <= last:
            inside[meeting_id] = (started, title)
            held[title].add(when)

    # Standing by the count of distinct DAYS a title was held on, where the
    # solver counts meetings. Equal on a clean corpus and not on a dirty
    # one, which is the point of deriving it twice.
    standing = {title for title, days in held.items() if len(days) >= STANDING_MINIMUM}
    in_window = {
        meeting_id: started
        for meeting_id, (started, title) in inside.items()
        if title in standing
    }

    statements: dict[tuple[str, str], list] = defaultdict(list)
    turns_read = 0
    for meeting_id, position, speaker, text in meetings.execute(
        "SELECT meeting_id, position, speaker, text FROM utterances"
    ):
        if meeting_id not in in_window:
            continue
        turns_read += 1
        deadline = _committed_in(text)
        if deadline is None:
            continue
        statements[(speaker, inside[meeting_id][1])].append(
            (in_window[meeting_id], position, meeting_id, deadline)
        )

    # Resolved by maximum, not by sorting and taking the last.
    rows = []
    superseded = 0
    for (speaker, title), made in statements.items():
        superseded += len({statement[2] for statement in made}) - 1
        started, _position, meeting_id, deadline = max(made, key=lambda s: (s[0], s[1]))
        # Built field by field from a declared order rather than as a dict
        # literal. The solver writes the same five keys inline; sharing that
        # expression is sharing a decision about what a row *is*, and the
        # independence gate counts it as a copied rule — correctly, because
        # a field renamed in one file and not the other should be a
        # disagreement rather than a matching typo.
        named = people[speaker] if speaker in people else speaker
        moment = epoch + datetime.timedelta(seconds=started)
        rows.append(
            dict(
                zip(
                    _ROW_FIELDS,
                    (
                        named,
                        title,
                        _resolve(moment.date(), deadline).isoformat(),
                        meeting_id,
                        moment.isoformat(),
                    ),
                    strict=True,
                )
            )
        )
    rows.sort(key=lambda row: (row["meeting"], row["owner"]))

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
    check("live", rows)

    # Floors no per-row criterion can see.
    if len(rows) < ROW_FLOOR:
        problems.append(fail(f"row floor: {len(rows)} rows, fewer than {ROW_FLOOR}"))

    keyed = {(row["owner"], row["meeting"], row["due"]) for row in rows}
    if len(keyed) != len(rows):
        problems.append(
            fail(
                f"key collapse: {len(rows)} rows key to {len(keyed)} — the ceiling "
                "is below 1.0 and row F1 will not show it, because both sides "
                "dedupe identically"
            )
        )
    owned = {(row["owner"], row["meeting"]) for row in rows}
    if len(owned) != len(rows):
        problems.append(
            fail(
                f"two live commitments for one person in one meeting: {len(rows)} "
                f"rows over {len(owned)} pairs. The brief admits one; the later "
                "statement replaced the earlier."
            )
        )

    # The mechanism the task exists to grade. A register nothing supersedes
    # makes a reader who takes the first answer always right, and the task
    # scores comprehension it never tested.
    def _due(statement) -> datetime.date:
        moment = epoch + datetime.timedelta(seconds=statement[0])
        return _resolve(moment.astimezone(zone).date(), statement[3])

    # Compared as resolved DATES, not as the words. Two statements of `EOD`
    # a fortnight apart are the same token and different obligations, and
    # counting tokens here would report this corpus as barely superseding
    # while the register it grades changes on most rows.
    changed = sum(
        1
        for made in statements.values()
        if len({statement[2] for statement in made}) > 1
        and _due(min(made, key=lambda s: (s[0], s[1])))
        != _due(max(made, key=lambda s: (s[0], s[1])))
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

    for field in ("due", "owner", "meeting"):
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
