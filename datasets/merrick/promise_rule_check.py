"""The promise rule again, walked in WORDS rather than in characters.

**This is the second derivation, and its whole value is being unlike the
first.** `promise_rule` splits clauses with a regex over characters and
matches deadline forms with compiled patterns. This tokenises, then walks
the token list. A task is only built when the two agree on every utterance
of the corpus, so a mistake in either shows up as a disagreement rather
than as a confident wrong answer.

Independence has to be at the level of *assumptions*, not just of code, and
that is a lesson this dataset paid for. An earlier pair of derivations
shared nothing textual and still encoded the same too-narrow reading of the
negation rule -- each citing the same justifying example, written months
apart -- and agreed with each other on all 2,872 utterances while eleven of
twenty rows were wrong. Nothing mechanical caught it; three model families
declining the same rows did.

So when these two disagree, neither is presumed right. Read the passage.

Vendored per task by `build_tasks`, single-sourced here, for the reason the
solver's copy is: two registers over the same prose must decide the same
question the same way, and a copy per task drifts.
"""

from __future__ import annotations

import datetime
import re

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

# Read off the brief's own table rather than spelled into `_resolve`, so a
# renamed token fails loudly at the lookup instead of silently falling
# through to the weekday walk and spinning.
_EOD = "eod"
_TOMORROW = "tomorrow"
_END_OF_WEEK = "end of week"
_FRIDAY = "friday"


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


# Words that join a second verb to the subject already standing. Checked
# only immediately before the verb: further back an `and` is as likely to
# be joining two subjects ("so Mira and I can close this out by tomorrow"),
# and blocking on that swallowed a real commitment.
_COORDINATORS = frozenset(("and", "or", "then"))


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
        # Two: at least one word of subject, then a finite verb in reach --
        # unless that verb is coordinated onto the speaker's own. A finite
        # verb whose immediately preceding word is `and`, `or` or `then` is
        # a second thing the SAME subject does, which the brief has always
        # said is not somebody else's clause. "I'll pull the criteria out
        # of that into a standalone comparison and have it to you by
        # Thursday" was refused for want of this, and the register carried
        # a superseded date for that person all epoch.
        for step in range(1, min(_SUBJECT_WIDTH, len(rest) - 1) + 1):
            if rest[step] in _FINITE and rest[step - 1] not in _COORDINATORS:
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
