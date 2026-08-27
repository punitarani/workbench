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


# The brief names `end of the day` alongside `end of day`, and the solver
# accepts the optional `the`. This list did not, so every "before the end
# of the day" was invisible here -- four hartwell mails, found only by
# running the pair over a corpus neither had seen. Enumerated rather than
# patterned, because this route enumerates on purpose.
def _with_the(form: str) -> tuple[str, ...]:
    """`end of day` and `end of the day`, wherever the first appears."""

    return (form, form.replace("end of day", "end of the day"))


ADMITTED: tuple[tuple[str, str], ...] = (
    ("EOD tomorrow", "tomorrow"),
    ("COB tomorrow", "tomorrow"),
    ("close of business tomorrow", "tomorrow"),
    ("end of day tomorrow", "tomorrow"),
    ("end of the day tomorrow", "tomorrow"),
    ("tomorrow EOD", "tomorrow"),
    ("tomorrow COB", "tomorrow"),
    ("tomorrow close of business", "tomorrow"),
    ("tomorrow end of day", "tomorrow"),
    ("tomorrow end of the day", "tomorrow"),
    *(
        (f"{day.title()} {form}", day)
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
        for form in ("EOD", "COB", "close of business", "end of day", "end of the day")
    ),
    *(
        (f"{form} {day.title()}", day)
        for form in ("EOD", "COB", "close of business", "end of day", "end of the day")
        for day in ("monday", "tuesday", "wednesday", "thursday", "friday")
    ),
    ("end of the week", "end of week"),
    ("end of week", "end of week"),
    ("EOW", "end of week"),
    ("close of business", "eod"),
    ("end of the day", "eod"),
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
# No `until`: it ends a wait rather than dating a delivery. See the note
# beside the solver's `_ATTACHES`; both derivations drop it, each having
# been checked against the corpus separately.
# No `for`: it schedules rather than dates. See the solver's `_ATTACHES`.
_INTRODUCES = ("by", "before", "due", "on", "come")

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


# Words a clock time occupies between the introducer and the day. The
# tokeniser splits `mid-morning` into `mid` and `morning`, so this is a
# short walk rather than a lookup. "by mid-morning tomorrow" is due
# tomorrow, and the solver widens its character window for the same reason.
_CLOCK = frozenset(
    ("mid", "morning", "midday", "noon", "day", "am", "pm", "first", "thing")
)


def _introduced(tokens: list[str], start: int) -> bool:
    """Whether an attaching preposition stands before the form."""

    at = start
    # Four steps, not three. `by 5:00 PM Friday` tokenises to `by`, `5`,
    # `00`, `pm`, `friday` -- three hops land on `5` and stop before ever
    # reaching the preposition, so the day looked unattached.
    for _ in range(4):
        if at > 0 and tokens[at - 1] in _INTRODUCES:
            return True
        if at > 0 and (
            tokens[at - 1] in _CLOCK
            or re.fullmatch(r"\d{1,2}(?:am|pm)?", tokens[at - 1] or "")
        ):
            at -= 1
            continue
        break
    return False


def _binding(tokens: list[str], end: int) -> bool:
    """Whether `at the latest` follows the form, making a fallback firm.

    Counted forward through an optional time of day rather than matched,
    which is this derivation's way of reaching the same place the solver
    reaches with a pattern. Without it "today or tomorrow at the latest"
    reads as two days offered and neither chosen; with it the second is
    the deadline, which is what the phrase is for.
    """

    at = end
    if at < len(tokens) and tokens[at] in _TIMES_OF_DAY:
        at += 1
    return tokens[at : at + 3] == ["at", "the", "latest"]


def _deadlines_after(tokens: list[str], after: int):
    """EVERY admitted form at or past `after`, in table order.

    A generator, not a single answer, and that matters. Returning only the
    first form committed this route to it: "I'll have the fee modeling to
    you by end of day Thursday so you can turn it around to Idris by
    Friday EOD" finds `Friday EOD` first, refuses it -- correctly, it is
    `you`'s deadline -- and then gave up, where the solver falls through
    to the Thursday that is actually the speaker's. Five disagreements
    across two corpora, and it read like a difference of interpretation
    until the brief was consulted: the brief decides it, and the solver
    was right.
    """

    yield from _admitted_forms(tokens, after)


def _admitted_forms(
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
            binding = _binding(tokens, end)
            if not binding and _offered_as_a_choice(tokens, start, end):
                continue
            introduced = _introduced(tokens, start)
            trails = end < len(tokens) and tokens[end] in _TIMES_OF_DAY
            ends_clause = end == len(tokens) or (trails and end + 1 == len(tokens))
            if not (binding or introduced or ends_clause):
                continue
            yield token, wanted, start, end


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
# `with` earns its place here on one row. "I'll update the Sandhurst
# checklist ... with Quentin's residual comments due tomorrow" dates
# QUENTIN's comments, and the register held it as Samir owing something.
# Three readers refused it unanimously. The brief already said a new
# subject marks somebody else's clause; `with` is simply another word that
# can introduce one, and it costs exactly this row across 4,271 items.
_CONNECTIVES = frozenset(
    (
        "with",
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
        # `until` opens a clause with a new subject. Deliberately NOT one of
        # the prepositions that can DATE a delivery: two lists, two
        # questions. See commitment-revision-register.
        "until",
        "and",
        "but",
    )
)
# Only `i`. `we` was here and the brief never put it there: "a new SUBJECT"
# marks somebody else's clause, and `we` is a different subject from `I`.
_SPEAKER = frozenset(("i",))

# A pronoun after a connective is a subject whatever verb follows, which
# the finite-verb list cannot cover: "and we each report back" has `report`.
_PRONOUN_SUBJECTS = frozenset(("we", "they", "you", "he", "she"))

# Only these introduce a pronoun that is acting as a SUBJECT. The full
# connective set includes prepositions like `with`, after which a pronoun
# is an object.
_COORDINATING = frozenset(("and", "so", "but", "then"))
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

# Words a subject may span before its verb.
#
# The reason recorded here was stale and would have led the next reader to
# widen it. It said four through ten were all equivalent -- "three
# defective rows go at every width and none of the thirteen sound ones do"
# -- which was true of an older rule over an older corpus. Re-measured
# against the whole 4,271 items as the rule stands now:
#
#     width 3, 4, 5   identical to 6
#     width 6         shipped
#     width 7, 8, 10  one SOUND row lost
#
# The plateau is 3-6, not 4-10, and 6 is its top rather than its middle.
# The row that goes at 7 is "I will review the linkage log myself tomorrow
# morning and sign off or tell you precisely what is missing by Thursday",
# where a wider window reaches `is` inside "what is missing" -- a relative
# clause, not a new subject.
_SUBJECT_WIDTH = 6


# Words that join a second verb to the subject already standing. Checked
# only immediately before the verb: further back an `and` is as likely to
# be joining two subjects ("so Mira and I can close this out by tomorrow"),
# and blocking on that swallowed a real commitment.
_COORDINATORS = frozenset(("and", "or", "then"))


# Words that open a condition. A day standing inside one is a day the
# promise is CONTINGENT on, not a day anything is due, and the brief says
# so with its own example. Kept separate from `_elsewhere`, which asks a
# different question -- whose clause is this -- and answers "the speaker's"
# for "if we're still waiting", where the day is still conditional.
# `once` sits with the trigger phrases below; see the solver's `_CONDITION`.
_CONDITIONALS = frozenset(("if", "unless", "whenever", "once"))
# An event trigger is a condition in other words: "the moment it's
# initialed tomorrow" dates the initialling. `the second` stays out --
# "the second request" is an ordinal, not a trigger.
_CONDITIONAL_PHRASES = (
    ("in", "case"),
    ("the", "moment"),
    ("the", "minute"),
    ("as", "soon"),
)


def _conditional(between: list[str]) -> bool:
    """Whether a condition opens between the promise and the day."""

    if any(word in _CONDITIONALS for word in between):
        return True
    pairs = zip(between, between[1:], strict=False)
    return any(pair in _CONDITIONAL_PHRASES for pair in pairs)


# The prepositions that can introduce a day, repeated here because this
# check asks a different question of them: not "is the day attached" but
# "attached to WHOSE noun".
_OWNING = frozenset(("by", "before", "due", "on", "come"))
# How far an owner's name may sit from the preposition it owns through.
# "Thandiwe's sign off by" is four tokens; two nouns is the most this firm
# writes before the preposition.
_OWNER_REACH = 5


ROSTER: frozenset[str] = frozenset()


def use_roster(names) -> None:
    """Name the people whose possessives own a day, before scanning.

    Set by the caller because this module is shared by every corpus in the
    tree and each has its own people. Empty removes the test rather than
    guessing from capitalisation.
    """

    global ROSTER
    ROSTER = frozenset(
        part.casefold() for full in names for part in full.split() if len(part) > 2
    )


def _roster() -> frozenset:
    return ROSTER


def _owned_elsewhere(between: list[str]) -> bool:
    """Whether the day's own noun belongs to somebody named.

    `_elsewhere` finds a new subject by its VERB. A possessive has no verb
    and owns the day just as plainly: "I'll add a caveat to the slide
    flagging that the Section III timeline assumes Thandiwe's sign-off by
    Wednesday" promises a caveat, and Wednesday is when Thandiwe signs.

    Asked of the END of the span only, so the question is who owns THIS
    day. Asked of the whole span it also refuses "And Bennett's right on
    Renwick: ... I'll have a firm date by end of day tomorrow", where the
    possessive sits in a different clause from the promise.

    `_tokens` splits on non-word characters, so a possessive arrives as the
    name followed by a bare `s` -- which is also how a contracted `is`
    arrives, and why this looks for a name rather than for any word.
    """

    if not between or between[-1] not in _OWNING:
        return False
    tail = between[-_OWNER_REACH - 1 : -1]
    roster = _roster()
    return any(
        word in roster and tail[index + 1] == "s"
        for index, word in enumerate(tail[:-1])
    )


# An indefinite person handed an infinitive is a new subject with no finite
# verb for `_elsewhere` to find. The brief settles it outright: "someone
# needs to own the EOD escalation call" *asks for a volunteer* and makes no
# row. Without this, "I'll need someone to confirm that's the only
# certificate needing a follow-up revision before Wednesday's close" was a
# row -- the confirming is the volunteer's, and so is the Wednesday.
_INDEFINITE = frozenset(("someone", "somebody", "anyone", "anybody", "everyone"))


def _volunteer(between: list[str]) -> bool:
    """Whether the span hands the act to an unnamed person."""

    for index, word in enumerate(between):
        if word not in _INDEFINITE:
            continue
        rest = between[index + 1 :]
        if rest and rest[0] == "else":
            rest = rest[1:]
        if len(rest) > 1 and rest[0] == "to":
            return True
    return False


def _elsewhere(between: list[str]) -> bool:
    """Whether somebody else's clause stands in `between`."""

    for index, word in enumerate(between):
        if word not in _CONNECTIVES:
            continue
        rest = between[index + 1 :]
        if not rest or rest[0] in _SPEAKER:
            continue
        # A pronoun subject settles it without consulting the verb list --
        # but only after a COORDINATOR. `with you` is a prepositional
        # object, not a subject, and "I'll plan to check in with you by end
        # of week" is a commitment; the wider connective set turned it into
        # somebody else's clause, and the solver's narrower one did not.
        # The two derivations disagreed on exactly that turn.
        if word in _COORDINATING and rest[0] in _PRONOUN_SUBJECTS and len(rest) > 1:
            return True
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
        # A question asks; it does not promise. The brief says so and this
        # file pinned the sentence without ever enforcing it.
        if clause.rstrip().endswith("?"):
            continue
        tokens = _tokens(clause)
        for owner in OWNER_FORMS:
            wanted = _tokens(owner)
            if not wanted:
                continue
            for start in range(len(tokens) - len(wanted) + 1):
                if tokens[start : start + len(wanted)] != wanted:
                    continue
                for token, form, _at, _ends in _deadlines_after(
                    tokens, start + len(wanted)
                ):
                    # A binding fallback outranks a condition, the same way
                    # it outranks a disjunction: "or by end of week at the
                    # latest" is the deadline whatever triggered the promise.
                    if not _binding(tokens, _ends) and _conditional(
                        tokens[start + len(wanted) : _at]
                    ):
                        continue
                    if _governed_negation(clause, wanted, form):
                        continue
                    between = tokens[start + len(wanted) : _at]
                    if _elsewhere(between):
                        continue
                    if _owned_elsewhere(between) or _volunteer(between):
                        continue
                    return token
    return None
