"""The promise rule: a first-person commitment and the day it falls due.

**One source, vendored per task.** `build_tasks` copies this beside every
solver that imports it, the way it already copies `criteria_base` beside
every `criteria.py`. Two tasks reading the same prose surface must apply
the same rule, and the alternative -- a copy per task -- is the drift this
dataset has already paid for twice: a window screen that chose a window on
a rule three versions old, and a verifier whose negation test was the
solver's from months earlier.

The rule itself was measured into its present shape rather than designed.
Its five conditions each removed rows that three model families had
declined and that reading the transcripts confirmed were not commitments.
`solve.py` in `live-commitment-register` carries that history in full;
what lives here is the part that is about English rather than about any
one surface, so a register over mail and a register over meeting
transcripts decide "is this a promise, and when is it due" identically.

What does NOT live here is anything about a corpus: no window, no
supersession unit, no notion of what a row is. Those differ per task and
belong to the task.
"""

from __future__ import annotations

import datetime as dt
import re
import sqlite3
from zoneinfo import ZoneInfo

WEEKDAYS = ("monday", "tuesday", "wednesday", "thursday", "friday")

# What a person says when the work is theirs. Measured on 56 recorded days:
# `I'll` 501 turns, `I will` 9, and nothing looser survives contact —
# `I have` is possession, `I'd` is conditional, and `I can` is as often
# `I can't` or `I can see why`. A chair recapping somebody else's promise
# ("Reinhardt, $61,047.00 out by Thursday") is not a commitment by anyone in
# the room: the person who owes it never said it, and the person who said it
# does not owe it.
OWNER_FORMS: tuple[str, ...] = (r"\bI'll\b", r"\bI will\b")

# The deadline forms this firm writes, and the token each normalises to.
# First match wins, so **order is the rule** and the compound comes first.
#
# `EOD tomorrow` is one deadline meaning end of day tomorrow, and a table
# that tries the bare `EOD` first reads it as the day it was said.
#
# The magnitude here was restated once and re-measured since, because the
# old figure -- "a quarter of everything graded" -- was taken on a smaller
# corpus and would not survive being checked. Measured now by mutation
# against all 4,271 items: moving the bare end-of-day form to the front of
# this table moves **20 of 222 verdicts**, and reversing the table moves
# 13. Nine per cent, not twenty-five, and still the largest single effect
# any ordering decision in this rule has.
#
# 43% of admitted turns name more than one form at all (the note used to
# say 40%, and that one held), so this is not an edge case dressed up as
# one. `tests/datasets/test_merrick_promise_rule_conditions.py` enforces
# the ordering; this comment only explains it.
# A gap between the words of a form is any run of space or punctuation, not
# a space. The firm writes `EOD-tomorrow` and `end-of-week` as readily as it
# writes them out, and a pattern anchored on `\s+` reads the hyphenated
# compound as a bare `EOD` and puts the deadline a day early — silently,
# because `eod` is a valid token that yields a plausible date. The
# independent verifier tokenises instead of matching, so it read those turns
# correctly and the two derivations disagreed by one supersession, which is
# how this was found rather than shipped.
_GAP = r"[\s\-\u2010-\u2015]+"


def _form(*words: str) -> str:
    return r"\b" + _GAP.join(words) + r"\b"


_EOD = rf"(?:EOD|COB|close{_GAP}of{_GAP}business|end{_GAP}of{_GAP}(?:the{_GAP})?day)"

DEADLINE_FORMS: tuple[tuple[str, str], ...] = (
    # Every compound, in either order, ahead of either part. This firm
    # writes all of them and each names ONE day: `EOD tomorrow` 79 turns,
    # `tomorrow EOD` 27, `<weekday> EOD` 6. A table that tries the bare
    # `EOD` first resolves every one of them to the day it was said —
    # silently, because `eod` is a valid token yielding a plausible date.
    (rf"\b{_EOD}{_GAP}tomorrow\b", "tomorrow"),
    (rf"\btomorrow{_GAP}{_EOD}\b", "tomorrow"),
    *((rf"\b{day}{_GAP}{_EOD}\b", day) for day in WEEKDAYS),
    *((rf"\b{_EOD}{_GAP}{day}\b", day) for day in WEEKDAYS),
    (rf"\b{_EOD}\b", "eod"),
    (rf"\b(?:EOW|end{_GAP}of{_GAP}(?:the{_GAP})?week)\b", "end of week"),
    (r"\btomorrow\b", "tomorrow"),
    *((rf"\b{day}\b", day) for day in WEEKDAYS),
)

_OWNER = re.compile("|".join(OWNER_FORMS), re.IGNORECASE)
_DEADLINE = tuple(
    (re.compile(pattern, re.IGNORECASE), token) for pattern, token in DEADLINE_FORMS
)


# A deadline named only to be ruled out. Measured on the record: 3 of 132
# commitment sentences, and all three real —
#
#   "treating it as urgent, not EOD"
#   "i'll get an answer today, not tomorrow"
#   "i'll flag it same day, not wednesday morning"
#
# In each the speaker's actual deadline is unstated or unadmitted (`today`,
# `same day`), so the sentence should make no row at all; matching the
# rejected form instead puts a commitment in the register that its owner
# explicitly disclaimed.
#
# Deliberately tight, and a looser rule was measured and discarded. Scanning
# a 28-character window for any negation flags 8 of 132, and five of those
# are false: in "I'll have a real number, not a guess, by end of day" the
# `not` belongs to the guess, and in "by Wednesday so it's not in Friday's
# crunch" the negation lands on a *later* form that first-match-wins never
# reaches. The negation has to sit immediately against the form.
# `_RULED_OUT` is SHADOWED inside `commitment_in`: remove it there and no
# verdict moves anywhere in 4,271 items, because `_negated` reaches every
# sentence it reaches and also knows that a comma ends a negation's reach.
# It is kept, and the distinction is worth stating. Shadowing comes in two
# kinds, and only one is dead weight:
#
#   logically shadowed   the wider test subsumes the narrower for ALL
#                        inputs. Delete it.
#   empirically shadowed this corpus never separates them. Keep it.
#
# This is the second. "I'll do X, not by Friday, but Monday" would fire
# `_RULED_OUT` and not `_negated` -- the comma ends the negation's reach
# for one and not the other -- and this firm simply never writes it. The
# check also has a second caller in `deadline_token`, which the shadowing
# test does not exercise at all.
_RULED_OUT = re.compile(
    r"\b(?:not|never|rather than|instead of)\s+"
    r"(?:by\s+|until\s+|waiting\s+for\s+)?$",
    re.IGNORECASE,
)


def deadline_token(text: str) -> str | None:
    """The deadline a turn names, normalised, or None.

    First match wins in declaration order, which is why the compound form
    leads the table. Collecting every form instead would make
    "I'll confirm by EOD tomorrow" name two deadlines, and a turn that
    disagrees with itself becomes a fake revision the moment supersession is
    computed by comparing a speaker's first statement to their last.
    """

    body = text or ""
    for pattern, token in _DEADLINE:
        for found in pattern.finditer(body):
            if _RULED_OUT.search(body[max(0, found.start() - 24) : found.start()]):
                continue
            return token
    return None


# A *clause*, for the purpose of pairing a promise with a date. Hard
# punctuation only -- terminator, semicolon, colon, dash.
#
# NOT `and`/`so`/`but`. This firm coordinates verb phrases under one
# subject, and "I'll have it edited and released by Wednesday" is one
# commitment: splitting on the conjunction loses seven of nine real rows.
# Measured, when a clause rule that did split there was tried.
_CLAUSE = re.compile(r"(?<=[.?!;:])\s+|\s*[\u2014\u2013]\s*|\s+-\s+")

# A negation between the promise and the date rules the date out -- but
# only while it still governs it, and a comma is what closes it off.
#
# Wider than `_RULED_OUT`, which reaches only an *adjacent* negator: the
# corpus writes "I'll cross-check same day ... so let's not slip that to
# Monday", where a whole verb phrase stands between `not` and `Monday`, and
# the shipped rule answered Monday -- the day the speaker refused.
#
# Narrower than "anywhere between", which was tried and eats a real
# deadline: in "I'll have a real number, not a guess, by end of day" the
# `not` belongs to the guess and the comma after it ends its reach. That
# sentence is a commitment for end of day, and a test already said so --
# which is how this bound was found rather than shipped.
# `n't` is here WITHOUT a leading `\b`, and that is the whole of a defect
# this table carried from the day it was written. In "doesn't" there is no
# word boundary between `s` and `n`, so `\bn't\b` matched no contraction
# anybody has ever typed -- a condition the brief promises and the rule
# could never apply. It cost four false rows, every one of them a date
# belonging to something the speaker was ruling OUT:
#
#   "I'll make sure Clement doesn't see it ... on Thursday"
#   "...if Reinhardt doesn't commit by end of day, it goes to Thandiwe"
#   "I'll chase Roland again if I haven't heard by Friday"
#   "...but 10.3 shouldn't be holding up Wednesday"
#
# Both derivations missed it and agreed with each other on all 4,271 items,
# which is what independence at the level of code rather than assumptions
# buys. An outside reader found it.
_NEG = re.compile(
    r"(?:\bnot\b|\bnever\b|n't\b|\brather than\b|\binstead of\b)", re.IGNORECASE
)


# Somebody else's clause, standing between the promise and the day.
#
# The brief has always said that reciting another person's deadline beside
# an undated promise makes no row. The clause rule catches it when the two
# are separated by hard punctuation and misses it when they are joined by a
# conjunction -- "I'll ping the moment I have it, Mira, so you can finalize
# the Officer's Certificate before tomorrow" dates Mira's work, and it was
# a row.
#
# What marks the boundary is a *new subject*, not the conjunction: this
# firm coordinates verb phrases under one subject constantly, and both of
# these are the speaker's own --
#
#   "...call Okafor myself today, not have an associate chase it, and I'll
#    have a firm date before Friday"     <- subject is `I`
#   "...escalate to a phone call today and can report back by EOD"
#                                        <- no subject at all: shared
#
# So: a connective, then at least one word that is not the speaker, then a
# finite verb. Measured over the sixteen rows at every gap from four words
# to ten; three defective rows go and none of the thirteen sound ones do,
# at every one of them. Six is the middle of that plateau.
_FINITE = (
    r"(?:can|could|will|would|shall|should|may|might|must|is|are|was|were"
    r"|has|have|had|do|does|did|lands?|happens?|holds?|comes?|goes)"
)
# The verb may be contracted onto its own subject -- `everyone's working`,
# `Clement doesn't see`, `the reporter's confirmed`. Without the first
# branch below the finite verb is invisible: a tokeniser splitting on
# non-word characters turns `everyone's` into `everyone` and `s`, and
# neither is in the table. That cost a row. Three model families declined
# `I'll update the checklist ... so everyone's working off the same
# document before it goes out tomorrow` nine times out of nine -- the
# `tomorrow` dates the document going out, not the promise -- and the
# register carried it anyway.
_ELSEWHERE = re.compile(
    r"\b(?:so|that|whether|which|because|if|once|when|while|unless|and|but|with)\s+"
    # `we` is NOT excluded, and it was, deliberately, for months. The
    # reasoning was that `we` includes the speaker so it cannot be somebody
    # else's clause. The brief says "a new SUBJECT does" mark it, and `we`
    # is a different subject from `I` -- which is why "so you can finalize
    # the Officer's Certificate before tomorrow" makes no row and "so we
    # can talk it through before Wednesday" is the same sentence wearing a
    # different pronoun. Four rows rested on the exclusion; readers refused
    # one of them 3-0 and the other three are the brief's own example.
    r"(?!i\b|i')"
    r"(?:[\w-]+(?:'s|'re|'ll|'ve|n't)\b"
    # A finite verb sitting immediately after `and`, `or` or `then` is
    # COORDINATED onto the speaker's own verb, not the verb of a new
    # clause. The brief has always said so -- "a conjunction alone does not
    # mark this... a new SUBJECT does" -- and without these lookbehinds the
    # rule contradicted it: "I'll pull the selection criteria out of that
    # into a standalone comparison and have it to you by Thursday" was
    # refused, because `that` was read as a connective and `have` as
    # somebody else's verb. Three model families disagreed and a panel of
    # readers sided with them.
    #
    # Only the verb-adjacent case. Blocking the coordinator anywhere in the
    # subject's reach also swallowed "so Mira and I can close this out by
    # tomorrow", where the `and` joins two SUBJECTS.
    r"|(?:[\w'-]+[\s,]+){1,6}?(?<!\band )(?<!\bor )(?<!\bthen )" + _FINITE + r"\b)",
    re.IGNORECASE,
)


def _negated(span: str) -> bool:
    """Whether a negator in `span` still governs what follows it."""

    return any("," not in span[found.end() :] for found in _NEG.finditer(span))


# A date is *attached* to a promise when a preposition introduces it or it
# ends the clause. A bare form mid-clause is a label, not a deadline: "the
# EOD escalation call" and "I'll defer the EOD escalation ownership to you"
# both name a task, and both were rows.
# `until` is deliberately absent. It marks the END of a waiting period, not
# a delivery deadline: "I'll hold off engaging outside counsel until
# Wednesday's call confirms the picture" promises INACTION, and the day
# belongs to the call. Exactly one commitment in 4,271 items attached its
# day this way and it was that one -- three readers refused it unanimously,
# citing the brief's own carve-out for a promise whose timing depends on an
# external event. Removing the word deletes a rule rather than adding one.
# Exactly the words the brief names, and nothing else. `for` and `end` were
# here and were never in the brief, so an agent following the brief to the
# letter disagreed with the key by construction -- readers refused a row
# 3-0 quoting the brief's own list back ("not one of the listed
# prepositions ... not `for`"). Measured by mutation rather than by
# matching: `for` decided 2 verdicts, both bad; `end` and `due` decide
# none; `come` decides 2 sound ones and is now named in the brief too.
#
# "for tomorrow morning" schedules the thing rather than dating the
# promise -- "I'll send the checkpoint reminder for tomorrow morning now"
# is due now -- which is why the word costs rows rather than earning them.
# A clock time may stand between the preposition and the day. "I'll get
# Rosalie the privilege-flag owner's name by mid-morning tomorrow" is due
# tomorrow, and the adjacency test could not see past `mid-morning`. The
# window widens with it: "by mid-morning " is fifteen characters and the
# old fourteen-character slice could not have held the preposition even if
# the pattern had allowed it.
#
# Found from the OTHER corpus. The delegation recording says "Rosalie owes
# me the draft by midday tomorrow", which resolved to the wrong day
# entirely -- the rule fell through `tomorrow` and matched a `Friday`
# later in the sentence. The same gap was sitting in merrick unexercised
# except once.
_ATTACHES_REACH = 26
_ATTACHES = re.compile(
    r"\b(?:by|before|due|on|come)"
    r"(?:\s+(?:mid-?morning|mid-?day|midday|noon|first thing"
    r"|\d{1,2}(?::\d{2})?\s*(?:am|pm)))?\W*$",
    re.IGNORECASE,
)
_CLAUSE_FINAL = re.compile(r"^[\s.,;:!?)\"\']*$")

# A day still ends its clause when only a time of day trails it. "I'll check
# with Noor first thing tomorrow morning" carries its deadline exactly as
# "by tomorrow" does: `morning` belongs to the date phrase, and reading it
# as proof the day sits mid-clause is what the bare clause-final test did.
# The cost was measurable rather than theoretical -- six of nine trials
# across three model families reported the commitment this dropped, and
# seven of nine put `superseded_count` above where the key had it.
_TIME_OF_DAY = re.compile(
    r"\s*(?:morning|afternoon|evening|night|a\.?m\.?|p\.?m\.?)(?!\w)",
    re.IGNORECASE,
)

# A day offered as one of two TIMES is a day nobody picked. "locked for
# Wednesday or Thursday afternoon" chooses a slot and "hold the tracker
# update until then or first thing tomorrow" offers two moments; in neither
# has the speaker named a deadline, and taking the first of the two was a
# row that cannot be graded at all -- whichever date the key holds, the
# other reading is as good.
#
# The alternative has to be another TIME, and it has to sit next to the
# `or`. An `or` joining two things to be DELIVERED leaves the deadline
# alone: "I'll have my sign-off or a specific open item by Thursday" is due
# Thursday, and so is "I'll sign off or tell you what is missing by
# Thursday" -- which a looser test, asking only whether any time word stood
# somewhere before the `or`, took away on the strength of an unrelated
# `tomorrow` earlier in the same clause.
_ALTERNATIVE_TIME = (
    "(?:then|now|today|tonight|later|tomorrow|saturday|sunday|"
    + "|".join(WEEKDAYS)
    + ")"
)
_ALTERNATIVE_BEFORE = re.compile(
    rf"\b{_ALTERNATIVE_TIME}\s+or\b[^.;:!?]{{0,24}}$", re.IGNORECASE
)
_ALTERNATIVE_AFTER = re.compile(rf"^\s*or\s+{_ALTERNATIVE_TIME}\b", re.IGNORECASE)

# `at the latest` is what English uses to make a fallback binding, and this
# firm writes it ten times. It settles the alternatives rather than being
# one of them: "sent over to you today or tomorrow at the latest" is due
# tomorrow, and "I'll flag the room the moment I hear back or by end of
# week at the latest" is due end of week. Readers given the second WITHOUT
# this rule split 2-1, one applying the disjunction rule and the others
# reading the fallback as the deadline -- a row nobody could be graded on.
_BINDING = re.compile(
    r"\s*(?:morning|afternoon|evening|night|a\.?m\.?|p\.?m\.?)?\s*at the latest\b",
    re.IGNORECASE,
)


# A day inside a CONDITION is not a deadline. The brief has said this from
# the beginning -- "if it's still open Wednesday EOD, flag me directly and
# I'll make the call ... names a date as a condition" -- and the rule only
# caught the cases where the condition also introduced a new subject.
#
# It does not, often. "only name it as a blocker if we're still waiting
# come tomorrow morning" has `we`, which `_ELSEWHERE` deliberately treats
# as the speaker; the day still belongs to the condition. Four rows rested
# on that, one of them declined by every trial of every tier.
# ...and an event TRIGGER is the same thing wearing different words. "I'll
# fold Elena's indemnity language into the checklist the moment it's
# initialed tomorrow" dates the initialling, not the folding, and the brief
# has always said a promise whose timing depends on an external event names
# no day at all. Two of three readers refused that row; every trial of the
# 182-day sweep declined it.
#
# `the second` is deliberately absent. This firm writes "the full text of
# the second request", and an ordinal is not a trigger.
# `once` belongs with `the moment` and `as soon as`, and was missing.
# "I'll report back once I have the signed doc in hand, hopefully before
# EOD" makes the report contingent on the counterparty signing; three
# readers refused it 3-0, quoting the brief's own carve-out for a promise
# whose timing depends on an external event. Exactly one verdict in 4,271
# items, found by applying the ASSIGNMENT rule's gate check to this rule's
# output -- a cross-check neither rule was designed for.
_CONDITION = re.compile(
    r"\b(?:if|unless|whenever|in case|once|the moment|as soon as|the minute)\b",
    re.IGNORECASE,
)


# A pronoun subject standing after a connective is a new subject even when
# no FINITE verb follows it. "and we each report back to Dov by end of day"
# has `report`, which is not on the finite list and never will be -- the
# list cannot enumerate English. The pronoun is the evidence.
_PRONOUN_SUBJECT = re.compile(
    r"\b(?:and|so|but|then)\s+(?:we|they|you|he|she)\s+(?!')[a-z]", re.IGNORECASE
)


def commitment_in(text: str) -> str | None:
    """The deadline this turn's speaker committed to, or None.

    Four conditions, each measured against the twenty rows the shipped rule
    produced. Nine of those were sound and eleven were not, and the eleven
    were found the only way this class can be found: three model families
    disagreed with the oracle in the same direction, and the transcripts
    agreed with the models.

    **1. The promise and the date share a CLAUSE, not a sentence.** The
    sentence rule replaced a turn rule for exactly this reason and did not
    go far enough. "Quick status round from my side: I've escalated ... and
    I'm expecting a written confirmation ... by end of day - I'll flag that
    to Priyanka the moment it lands" is one sentence, and the `end of day`
    belongs to the docketing manager's confirmation, not to the flag.

    **2. The date follows the promise.** "Wednesday it is, Dov, I'll expect
    it closed by then" recites a date somebody else owns before promising to
    watch it.

    **3. The date is attached** -- a preposition introduces it, or it ends
    the clause. Both forms occur: "released by Wednesday" and "I'll have the
    scope and timeline doc to Clement Thursday". A bare form mid-clause
    modifies a noun instead: "I'll defer the EOD escalation ownership to
    you" is a hand-off, and it was a row.

    **4. Nobody else's clause stands between them.** "I'll ping the moment
    I have it, Mira, so you can finalize the Officer's Certificate before
    tomorrow" dates Mira's work. A conjunction alone does not mark this --
    "and I'll have a firm date before Friday" and "and can report back by
    EOD" are both the speaker's -- a new *subject* does.

    **5. No negation that still governs the date stands between them.**
    "so let's not slip that to Monday" answered Monday. A comma ends a
    negation's reach, so "I'll have a real number, not a guess, by end of
    day" keeps its deadline.

    Every owner form in the clause is tried, not only the first. The firm
    writes "I'll pull the EPO register directly rather than rely on the
    annuity service snapshot, and I'll close it out on Schedule 2 before
    EOD", where the `rather than` hanging off the first promise has nothing
    to do with the deadline hanging off the second.

    What this does NOT do is judge whether the speaker's verb is a delivery.
    "I owe Imelda a firm closing date by tomorrow morning and I'll beat
    that" is a real commitment that makes no row, because the brief admits
    `I'll` and `I will` and nothing looser -- and that is a statement about
    the rule, which the brief makes out loud, rather than a defect.
    """

    for clause in _CLAUSE.split(text or ""):
        for owner in _OWNER.finditer(clause):
            for pattern, token in _DEADLINE:
                for found in pattern.finditer(clause):
                    start, end = found.start(), found.end()
                    if _RULED_OUT.search(clause[max(0, start - 24) : start]):
                        continue
                    if start < owner.end():
                        continue
                    if _BINDING.match(clause[end:]) is None and _CONDITION.search(
                        clause[owner.end() : start]
                    ):
                        continue
                    if _negated(clause[owner.end() : start]):
                        continue
                    tail = clause[end:]
                    binding = _BINDING.match(tail) is not None
                    if not binding and (
                        _ALTERNATIVE_BEFORE.search(clause[owner.end() : start])
                        or _ALTERNATIVE_AFTER.match(tail)
                    ):
                        continue
                    trailing = _TIME_OF_DAY.match(tail)
                    if not (
                        binding
                        or _ATTACHES.search(
                            clause[max(0, start - _ATTACHES_REACH) : start]
                        )
                        or _CLAUSE_FINAL.match(tail)
                        or (trailing and _CLAUSE_FINAL.match(tail[trailing.end() :]))
                    ):
                        continue
                    if _ELSEWHERE.search(
                        clause[owner.end() : start]
                    ) or _PRONOUN_SUBJECT.search(clause[owner.end() : start]):
                        continue
                    return token
    return None


def due_date(said_on: dt.date, token: str) -> dt.date:
    """The calendar date a token names, said on `said_on`.

    Every branch here is a convention the corpus exercises, which is why the
    brief states each one rather than listing them for completeness:

    * `eod` is the day it was said. The meeting is in the morning and the
      commitment is for that evening.
    * `tomorrow` is the next **working** day, so said on a Friday it means
      Monday. The firm records no weekend days at all — 58 recorded days,
      every one Monday to Friday — so a Saturday deadline would be a date on
      which nobody could deliver.
    * `end of week` is that week's Friday, and said *on* a Friday it means
      that same day rather than a week later.
    * a weekday names its **next** occurrence, strictly after the day it was
      said. Said on a Thursday, "Thursday" is next Thursday — that happens
      in 3 turns — and a weekday earlier in the week than the meeting is
      next week's, which happens in 26.
    """

    if token == "eod":
        return said_on
    if token == "tomorrow":
        nxt = said_on + dt.timedelta(days=1)
        while nxt.weekday() >= 5:
            nxt += dt.timedelta(days=1)
        return nxt
    if token == "end of week":
        return said_on + dt.timedelta(days=(4 - said_on.weekday()) % 7)
    ahead = (WEEKDAYS.index(token) - said_on.weekday()) % 7
    return said_on + dt.timedelta(days=ahead or 7)


def _epoch(connection: sqlite3.Connection) -> tuple[dt.datetime, ZoneInfo]:
    """The run's own epoch and timezone, from the surface that serves them.

    `meetings.started` is an offset in seconds from this epoch, **not a Unix
    timestamp**. Read as one it yields 1970 dates that parse, sort and
    compare perfectly well while putting 30% of the firm's meetings on a
    weekend — a fidelity defect that does not exist, discovered only because
    the recorded day labels disagreed.
    """

    meta = dict(connection.execute("SELECT key, value FROM meta"))
    zone = ZoneInfo(meta["timezone"])
    return dt.datetime.fromisoformat(meta["epoch"]).astimezone(zone), zone
