"""Reference solver: the live commitment register.

One rule, and the whole difficulty is in the second half of it.

**A commitment is two things at once**: somebody speaking about their own
work, and a day named in the same turn. **A person owes one thing per
standing meeting: the most recent thing they said in it.** When the same
person names a day again in a later meeting of the same series, the later
statement replaces the earlier one entirely — not a second row, not a note,
simply no longer what they owe.

**What is graded is the date, not the word.** A deadline said out loud is
relative: `EOD`, `tomorrow`, `Thursday`. Two people saying `EOD` three weeks
apart owe different days, and so does one person saying it twice. The
register reports the resolved calendar date, which means a reader who has
the right owner and the right series but the wrong *meeting* still gets the
row wrong. That is the whole mechanism, and it is measured: grading the
token gives a reader who guesses the commonest word 47-69% of the field for
free, and grading the date gives them 16-23%.

**Why there is no matter column**, though an earlier draft of this task had
one and its removal is the reason this file was rewritten. The brief said "a
commitment about a matter"; a solver can only implement "a turn containing a
commitment token, a date token and a matter token". Measured on 56 recorded
days those are different rules: of 178 turns carrying a commitment and a
deadline only 63 name a matter, so the rule discarded 65% of the firm's real
promises for a reason unrelated to whether a promise was made — and in a
third of the 63 it kept, the matter name sat more than 120 characters from
the commitment, a different sentence of a 71-word turn. One qualifying turn
attached a promise to a matter in the clause where the speaker said she had
*nothing* on it.

The general form is worth stating once, because it will come up again: **a
conjunctive rule is safe only when its conjuncts share a unit.** Who is
speaking and what day they named are properties of a turn. Which piece of
work a promise is about is a property of a clause, and no care in the brief
turns a regex over a turn into a reader of clauses. Owner, series and date
are all turn-scoped, so the register is keyed on those and on nothing else.

That is also why this reads meetings rather than mail. Every other surface
in this world can be flattened by a script: `list_activities` returns all
21,597 time entries in about seventy seconds at zero context cost, and the
arithmetic over them is three lines. A transcript has no id to group by and
no column to sum, so the only way to know what was said is to read it.

**The oracle is computed the way the register is defined**, and
`checks/verify.py` derives the same answer by a second route from the
brief's own prose, so a rule that drifts between them is visible rather than
silently agreed.

Every `measure()` below is a value this world has not finished recording.
The guard raises rather than being a placeholder that is a syntax error: the
file compiles, the schema and independence gates can read it, and running it
before the measurement lands fails loudly with the question still open. The
date arithmetic deliberately sits above that line — it is a property of the
English, not of the recording, so it is written, tested and settled now.
"""

from __future__ import annotations

import collections
import datetime as dt
import json
import os
import re
import sqlite3
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))


STATE = Path(os.environ["WORKBENCH_STATE"])
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("live_commitments.json")

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
# `EOD tomorrow` is one deadline meaning end of day tomorrow, and it is the
# single commonest two-form phrase in the corpus: 47 of 178 commitment turns.
# A table that tries `EOD` before it resolves a quarter of everything graded
# to the wrong day. 40% of commitment turns name two forms at all, so this
# is not an edge case dressed up as one.
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

# How many times a title has to appear in the window before the meeting is a
# *standing* one rather than a one-off.
#
# The register is keyed on the series, so a one-off is a key with exactly one
# meeting in it: nothing can supersede, and the key is a free-text title the
# agent has to reproduce character for character. This world writes two of
# those a colon apart — `Ardmore Chain-of-Access Routing Decision` and
# `Ardmore Chain-of-Access: Routing Decision` — which are one meeting to a
# reader and two rows to a grader.
#
# The calendar cannot answer this, though it looks as though it should:
# `event_recurrence` is a real table that the projection never writes, so
# every event in the recorded world is served `recurrence: []` even though
# the workplace spec declares these eight meetings daily or weekly. So the
# series are recovered by counting, and the threshold is measured rather than
# picked: across four windows the standing series occur 4 to 32 times and the
# one-offs 1 or 2, so any cut in 3..4 separates them. Three is chosen because
# a 30-day window puts the weekly series at 4 and a cut of 5 would silently
# drop five of the eight.
STANDING_SERIES_MINIMUM = 3

_OWNER = re.compile("|".join(OWNER_FORMS), re.IGNORECASE)
_DEADLINE = tuple(
    (re.compile(pattern, re.IGNORECASE), token) for pattern, token in DEADLINE_FORMS
)


def _window() -> tuple[int, int]:
    """The window, in seconds from the run epoch, inclusive of both ends.

    A meeting is in the window when it **started** inside it; one that runs
    past the last day is still that day's meeting.

    «MEASURE: the window. `datasets/merrick/measure_transcripts.py` prints
    meetings, turns and words per window and refuses over 60,000 words or
    under 25 meetings. On 56 partial days of v6, days 20-64 held 140
    meetings and 50,113 words — inside the ceiling — and yielded 32 rows of
    which a first-answer reader got 72% wrong, against 26 rows at 69% for
    days 20-49. Longer is better until the ceiling binds, because
    supersession accumulates with time. Re-measure on the finished record:
    every figure here is from a recording that was 43% complete.»

    Probed end to end on the partial bundle at days 20-64, which is the
    shape recommended when the recording finishes: 131 standing meetings,
    660 turns, 28 rows over 7 series, 62 supersessions, 17 distinct due
    dates with the commonest holding 14%. A reader who takes each person's
    first statement finds every row — `row_f1` 1.000 keyed on
    (owner, meeting) — and scores **0.179** once the date joins the key,
    because they get the due date wrong on 82% of rows and report
    `superseded_count` as 0.

    Called rather than evaluated at import so the pure date arithmetic below
    can be tested without a corpus.
    """

    # Named `WINDOW_FIRST_DAY` / `WINDOW_LAST_DAY` because `build_tasks`
    # reads the window off this source to tell the verifier which window to
    # re-derive, and those are the names it looks for. It tolerates the
    # indentation, so the window can live in here and the rest of the
    # module -- the date arithmetic, the form tables -- stays importable
    # before the corpus exists.
    WINDOW_FIRST_DAY = 1
    WINDOW_LAST_DAY = 182
    return WINDOW_FIRST_DAY * 86_400, (WINDOW_LAST_DAY + 1) * 86_400 - 1


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
    r"(?!i\b|i'|we\b|we')"
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
_ATTACHES = re.compile(r"\b(?:by|before|due|on|come)\W*$", re.IGNORECASE)
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
_CONDITION = re.compile(r"\b(?:if|unless|whenever|in case)\b", re.IGNORECASE)


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
                    if _CONDITION.search(clause[owner.end() : start]):
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
                        or _ATTACHES.search(clause[max(0, start - 14) : start])
                        or _CLAUSE_FINAL.match(tail)
                        or (trailing and _CLAUSE_FINAL.match(tail[trailing.end() :]))
                    ):
                        continue
                    if _ELSEWHERE.search(clause[owner.end() : start]):
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


def main() -> int:
    low, high = _window()
    connection = sqlite3.connect(f"file:{STATE / 'meetings.db'}?mode=ro", uri=True)
    epoch, zone = _epoch(connection)
    people = dict(
        sqlite3.connect(f"file:{STATE / 'clio.db'}?mode=ro", uri=True).execute(
            "SELECT person_id, name FROM people"
        )
    )

    window = {
        meeting_id: (started, title)
        for meeting_id, started, title in connection.execute(
            "SELECT meeting_id, started, title FROM meetings"
        )
        if low <= started <= high
    }
    standing = {
        title
        for title, count in collections.Counter(
            title for _started, title in window.values()
        ).items()
        if count >= STANDING_SERIES_MINIMUM
    }
    window = {
        meeting_id: row for meeting_id, row in window.items() if row[1] in standing
    }
    turns = [
        row
        for row in connection.execute(
            "SELECT meeting_id, position, speaker, text FROM utterances"
        )
        if row[0] in window
    ]
    connection.close()

    said: dict[tuple[str, str], list] = {}
    for meeting_id, position, speaker, text in turns:
        token = commitment_in(text or "")
        if token is None:
            continue
        started, title = window[meeting_id]
        said.setdefault((speaker, title), []).append(
            (started, position, meeting_id, token)
        )

    live, superseded = [], 0
    for (speaker, title), occasions in said.items():
        occasions.sort()
        superseded += len({row[2] for row in occasions}) - 1
        started, _position, meeting_id, token = occasions[-1]
        moment = epoch + dt.timedelta(seconds=started)
        live.append(
            {
                "owner": people.get(speaker, speaker),
                "meeting": title,
                "due": due_date(moment.date(), token).isoformat(),
                "meeting_id": meeting_id,
                "said_at": moment.isoformat(),
            }
        )
    live.sort(key=lambda row: (row["meeting"], row["owner"]))

    OUT.write_text(
        json.dumps(
            {
                "meetings_read": len(window),
                "turns_read": len(turns),
                "distinct_owners": len({row["owner"] for row in live}),
                "superseded_count": superseded,
                "live": live,
            },
            indent=2,
        )
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
