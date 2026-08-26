"""An independent derivation of the same answer.

    WORKBENCH_STATE=out/merrick/bundle/state uv run python \
        datasets/merrick/tasks/standing-commitment-register/checks/verify.py

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
# Pinned against the filled brief for days 1-35 of the v7 record. Three
# sections, and only three: each states a rule this file derives
# independently. The window prose is not pinned -- it is a fact about which
# meetings to read, not a rule this file implements.
#
# `## Which one is live` also carries the measured supersession share, so it
# re-pins whenever the WINDOW moves and not only when the rule does. Kept:
# the share is what tells a reader the rule is worth applying, and splitting
# it out would leave the rule's own justification unpinned.
PINNED: dict[str, str] = {
    "## What counts as a commitment": "d54f8c426cfa7b8e",
    "## Turning what was said into a date": "c8f8a8253e49bbef",
    "## Which one is live": "42225d116aea964f",
    # The criteria themselves. `superseded_count` is DEFINED here and
    # graded, and this section was not pinned: its unit could be reworded
    # without tripping anything. Three readers of the old wording split
    # 2-1 on it while all three called it unambiguous.
    "## What to produce": "ae23c1dd4077f269",
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
WINDOW_FIRST_DATE = "2026-01-06"
WINDOW_LAST_DATE = "2026-07-06"

# «MEASURE: the admitted deadline forms and their normalised tokens, read
# out of the brief's own table rather than restated here once the table
# exists. Until then this is the question. Include the relative forms —
# a weekday-only rule was measured dead on this world: 14% of turns name a
# weekday against 41% naming a relative deadline, and the weekday-only
# register held six rows with no supersession at all.»
# Read off the brief's table, longest first: `_deadline` returns on the
# first form whose tokens appear, so a compound must precede either part or
# "EOD tomorrow" resolves as "eod" and loses a day. Both directions,
# because the corpus writes it both ways.
#
# The TOKEN is compared against `day.strftime("%A").casefold()`, so weekday
# tokens are lower case; the FORM is casefolded by `_tokens`. Writing a
# token capitalised walked the calendar to date.max looking for a day
# called "Monday" -- an OverflowError rather than a wrong answer, and only
# because that loop has no bound.
ADMITTED: tuple[tuple[str, str], ...] = (
    ("EOD tomorrow", "tomorrow"),
    ("COB tomorrow", "tomorrow"),
    ("close of business tomorrow", "tomorrow"),
    ("end of day tomorrow", "tomorrow"),
    ("tomorrow EOD", "tomorrow"),
    ("tomorrow COB", "tomorrow"),
    ("tomorrow close of business", "tomorrow"),
    ("tomorrow end of day", "tomorrow"),
    *(
        (f"{day.title()} {form}", day)
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
        for form in ("EOD", "COB", "close of business", "end of day")
    ),
    *(
        (f"{form} {day.title()}", day)
        for form in ("EOD", "COB", "close of business", "end of day")
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
    ),
    ("end of week", "end of week"),
    ("EOW", "end of week"),
    ("close of business", "eod"),
    ("end of day", "eod"),
    ("EOD", "eod"),
    ("COB", "eod"),
    ("tomorrow", "tomorrow"),
    ("Monday", "monday"),
    ("Tuesday", "tuesday"),
    ("Wednesday", "wednesday"),
    ("Thursday", "thursday"),
    ("Friday", "friday"),
)

# «MEASURE: the owner-shaped phrasings, likewise from the brief.»
# The brief names two and says "Nothing looser counts", so this is closed.
# An earlier draft gave only an EXAMPLE of an owner form and left the
# boundary open; Opus generalised from it, correctly by the brief's own
# words, and scored 22 rows against 33 -- which measures agreement with a
# regex rather than comprehension.
OWNER_FORMS: tuple[str, ...] = ("I'll", "I will")

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
        # The clause boundary, and that it is NOT the conjunction. A brief
        # that said "sentence" was graded against a clause rule for three
        # sweeps: eleven of twenty oracle rows paired a promise with a date
        # from a neighbouring clause, and three model families declined all
        # eleven. They were reading the brief; the brief was not stating the
        # rule its own oracle applied.
        "in the same clause",
        'does *not* end at "and", "so" or "but"',
        # The three attachment conditions, each of which removed rows.
        "day comes after the promise",
        "attached to the promise",
        "nobody else's clause stands between the promise and the day",
        "a new subject does",
        "no negation stands between the promise and the day",
        "a comma ends a negation's reach",
        "named only to rule it out is not a deadline",
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


# The words that rule a deadline out rather than name one, and the
# connectives allowed to sit between them and the form. Counted in tokens
# here; the solver scans characters. A form ruled out is not the speaker's
# deadline — "i'll flag it same day, not wednesday morning" commits to
# nothing this register admits — and matching it anyway puts a commitment in
# the answer that its owner explicitly disclaimed.
_RULES_OUT = ("not", "never")
_RULES_OUT_PHRASES = (("rather", "than"), ("instead", "of"))
_BRIDGES = ("by", "until", "waiting", "for")


def _ruled_out(tokens: list[str], start: int) -> bool:
    """Whether the form beginning at `start` is preceded by a negation.

    Walks back over the connectives a negation may put between itself and
    the form, then asks whether what stands before them negates. Deliberately
    short-sighted: on the record a window wide enough to reach past an
    intervening noun phrase flags five sentences that are not negations at
    all — in "a real number, not a guess, by end of day" the `not` belongs to
    the guess.
    """

    index = start
    while index > 0 and tokens[index - 1] in _BRIDGES:
        index -= 1
    if index > 0 and tokens[index - 1] in _RULES_OUT:
        return True
    return index > 1 and (tokens[index - 2], tokens[index - 1]) in _RULES_OUT_PHRASES


def _deadline(tokens: list[str]) -> str | None:
    for form, token in ADMITTED:
        wanted = _tokens(form)
        if not wanted:
            continue
        for start in range(len(tokens) - len(wanted) + 1):
            if tokens[start : start + len(wanted)] != wanted:
                continue
            if _ruled_out(tokens, start):
                continue
            return token
    return None


# The words that may introduce a deadline. A form they do not introduce has
# to end its clause instead, or it is naming a thing rather than a date --
# "the EOD escalation call" is a meeting, not a Tuesday.
_INTRODUCES = ("by", "before", "until", "due", "on", "come", "for")

# The nouns that may trail a day and leave it still ending its clause.
# Counted to the end of the clause rather than matched: "first thing
# tomorrow morning" is one word short of ending, and a rule that demands
# the day be the last word drops it. The solver steps a pattern over the
# same noun; both had to change, because between them they were losing two
# commitments and inventing none.
_TIMES_OF_DAY = ("morning", "afternoon", "evening", "night", "am", "pm")

# A time standing beside `or` makes the day next to it one of two offers.
# "today or tomorrow", "Wednesday or Thursday afternoon" and "until then or
# first thing tomorrow" each leave the speaker's own date unpicked, and a
# derivation that picks for them asserts a deadline nobody stated.
#
# `then` and `now` earn their place here: without them the third example
# reads as a plain commitment, and it is the one whose readers split.
_TIME_WORDS = (
    "then",
    "now",
    "today",
    "tonight",
    "later",
    "tomorrow",
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)

# How far the `or` may sit from the day it disqualifies. "until then or
# first thing tomorrow" puts two words between them; "sign off or tell you
# precisely what is missing by Thursday" puts seven, and there the `or`
# joins two deliverables rather than two times. The solver caps the same
# gap in characters.
_CHOICE_REACH = 4


def _offered_as_a_choice(tokens: list[str], start: int, end: int) -> bool:
    """Whether the form at `start`..`end` is one of two times joined by `or`."""

    for step in range(1, _CHOICE_REACH + 2):
        at = start - step
        if at < 1:
            break
        if tokens[at] == "or":
            if tokens[at - 1] in _TIME_WORDS:
                return True
            break
    return (
        end + 1 < len(tokens) and tokens[end] == "or" and tokens[end + 1] in _TIME_WORDS
    )


def _deadline_after(
    tokens: list[str], after: int
) -> tuple[str, list[str], int, int] | None:
    """The first admitted form that starts at or past `after` and *attaches*.

    Returns the form's token, the words it matched, and its span. The
    caller needs all three: the words to find the same form again in a
    comma-preserving split, and the span to know where it sat. The solver
    reads characters and this reads words, so the two agree on the answer
    by different routes and disagree loudly when one of them is wrong.
    """

    for form, token in ADMITTED:
        wanted = _tokens(form)
        if not wanted:
            continue
        for start in range(after, len(tokens) - len(wanted) + 1):
            if tokens[start : start + len(wanted)] != wanted:
                continue
            if _ruled_out(tokens, start):
                continue
            end = start + len(wanted)
            if _offered_as_a_choice(tokens, start, end):
                continue
            introduced = start > 0 and tokens[start - 1] in _INTRODUCES
            trails = end < len(tokens) and tokens[end] in _TIMES_OF_DAY
            ends_clause = end == len(tokens) or (trails and end + 1 == len(tokens))
            if not (introduced or ends_clause):
                continue
            return token, wanted, start, end
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


def _clauses(text: str) -> list[str]:
    """The turn as clauses: sentences, cut again at colons and dashes.

    A sentence is not small enough. "Quick status round from my side: I've
    escalated ... by end of day - I'll flag that to Priyanka the moment it
    lands" is one sentence in which the deadline belongs to the docketing
    manager and the promise carries none, and the register carried it as a
    row.

    Deliberately NOT cut at `and`/`so`/`but`. This firm coordinates verb
    phrases under one subject, and cutting there loses "I'll have it edited
    and released by Wednesday" -- seven of nine real rows, when a rule that
    did cut there was measured.
    """

    out: list[str] = []
    for sentence in _sentences(text):
        current: list[str] = []
        index = 0
        while index < len(sentence):
            character = sentence[index]
            following = sentence[index + 1 : index + 2]
            is_dash = character in "\u2014\u2013" or (
                character == "-"
                and following.isspace()
                and current
                and current[-1].isspace()
            )
            if character == ":" and (following == "" or following.isspace()):
                current.append(character)
                out.append("".join(current))
                current = []
            elif is_dash:
                out.append("".join(current))
                current = []
            else:
                current.append(character)
            index += 1
        if current:
            out.append("".join(current))
    return [clause for clause in out if clause.strip()]


# A connective, a subject that is not the speaker, and a finite verb: the
# shape of somebody else's clause. The solver expresses this as one regex
# over characters; this walks words, so the two reach the same boundary by
# different routes and a turn they disagree about is a finding.
_CONNECTIVES = frozenset(
    (
        "so",
        "that",
        "whether",
        "which",
        "because",
        "if",
        "once",
        "when",
        "while",
        "unless",
        "and",
        "but",
    )
)
_SPEAKER = frozenset(("i", "we"))
_FINITE = frozenset(
    (
        "can",
        "could",
        "will",
        "would",
        "shall",
        "should",
        "may",
        "might",
        "must",
        "is",
        "are",
        "was",
        "were",
        "has",
        "have",
        "had",
        "do",
        "does",
        "did",
        "land",
        "lands",
        "happen",
        "happens",
        "hold",
        "holds",
        "come",
        "comes",
        "goes",
    )
)
# What a contraction leaves behind once the tokeniser has split on the
# apostrophe: `everyone's` -> `everyone`, `s`; `doesn't` -> `doesn`, `t`.
# These are finite verbs ONLY when attached to the subject that opens the
# clause. Put in the general table instead, they fire on any possessive in
# reach -- `that the Section III timeline assumes Thandiwe's sign-off by
# Wednesday` became somebody else's clause, and the two derivations
# disagreed on four turns.
_CONTRACTED = frozenset(("s", "re", "ll", "ve", "t", "m"))

# Words a subject may span before its verb. Measured at four through ten
# on the sixteen rows: three defective rows go at every width and none of
# the thirteen sound ones do. Six is the middle of that plateau.
_SUBJECT_WIDTH = 6


def _elsewhere(between: list[str]) -> bool:
    """Whether somebody else's clause stands in `between`."""

    for index, word in enumerate(between):
        if word not in _CONNECTIVES:
            continue
        rest = between[index + 1 :]
        if not rest or rest[0] in _SPEAKER:
            continue
        # One: the verb is contracted onto the subject opening the clause.
        if len(rest) > 1 and rest[1] in _CONTRACTED:
            return True
        # Two: at least one word of subject, then a finite verb in reach.
        for step in range(1, min(_SUBJECT_WIDTH, len(rest) - 1) + 1):
            if rest[step] in _FINITE:
                return True
    return False


def _governed_negation(clause: str, owner_form: list[str], day_form: list[str]) -> bool:
    """Whether a negator between the promise and the day still reaches it.

    Commas are kept here and dropped by `_tokens`, because a comma is
    exactly what ends a negation's reach: in "I'll have a real number, not
    a guess, by end of day" the `not` belongs to the guess and the deadline
    survives, while in "so let's not slip that to Monday" nothing stands
    between the two and the day is refused.

    Only the words BETWEEN the promise and the day are considered. Scanning
    to the end of the clause instead put 26 utterances in disagreement with
    the solver -- a negation *after* the deadline says nothing about it.

    The solver decides the same thing by looking for a comma character
    after the negator. This counts comma *tokens*, so the two reach the
    boundary by different routes.
    """

    marked = [
        piece.casefold() for piece in re.split(r"([,])|[^\w,]+", clause or "") if piece
    ]

    def _at(words: list[str], start: int) -> int | None:
        return next(
            (
                index
                for index in range(start, len(marked) - len(words) + 1)
                if marked[index : index + len(words)] == words
            ),
            None,
        )

    head = _at(owner_form, 0)
    if head is None:
        return False
    day = _at(day_form, head + len(owner_form))
    if day is None:
        return False
    between = marked[head + len(owner_form) : day]
    for index, word in enumerate(between):
        following = between[index + 1] if index + 1 < len(between) else None
        pair = (word, following) if following is not None else None
        contracted = following == "t" and word.endswith("n")
        if word in _RULES_OUT or pair in _RULES_OUT_PHRASES or contracted:
            # A contracted negation occupies two tokens here, because the
            # apostrophe is a split point: "doesn't" arrives as `doesn`,
            # `t`. Its reach therefore starts after the `t`, and reading
            # from the wrong token would let the negation's own second half
            # stand in for the comma that ends it.
            reach = between[index + 2 :] if contracted else between[index + 1 :]
            if "," not in reach:
                return True
    return False


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

    for clause in _clauses(text):
        tokens = _tokens(clause)
        for owner in OWNER_FORMS:
            wanted = _tokens(owner)
            if not wanted:
                continue
            for start in range(len(tokens) - len(wanted) + 1):
                if tokens[start : start + len(wanted)] != wanted:
                    continue
                found = _deadline_after(tokens, start + len(wanted))
                if found is None:
                    continue
                token, form, _at, _ = found
                if _governed_negation(clause, wanted, form):
                    continue
                if _elsewhere(tokens[start + len(wanted) : _at]):
                    continue
                return token
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
