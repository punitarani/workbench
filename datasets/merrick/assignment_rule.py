"""Who somebody ELSE owes something to, and by when.

The sibling of `promise_rule`. That one reads `I'll ...` and asks what the
speaker committed to; this reads `<Name> owes ...` and asks what the room
was told somebody else owes. It is the family four recorded worlds could
not host -- the anchored third-person form appears 1, 8, 14 and 0 times
across them -- and which `probe_delegation` unblocked by changing one
sentence in each persona's spec.

**A sibling, not a subject-swap, and the difference was measured.** The
first draft of this reused `promise_rule` whole and changed only the owner
pattern. On the 45-day recording that admits 15 of 44 candidate clauses,
and the fourteen it drops are mostly real:

    "Samir has cap table recon to Elena EOD tomorrow"
    "Adaora owes clean MIP mechanics Thursday COB"
    "Rosalie has confirmed ownership ... with an EOD-tomorrow delivery"

None carries a preposition, none ends its clause. The assignment idiom
attaches its day by bare APPOSITION, which the first-person idiom rarely
does, so the attachment test that makes `promise_rule` precise makes this
one deaf. Removing it lifts recall to 33 of 44 -- and lets in seven false
rows, because a bare trailing day is exactly what `promise_rule` spent
four of its corrections learning to refuse.

So the licence to read a bare day is granted here and paid for with three
conditions of this rule's own, each measured on the recording and each
removing only what it was aimed at:

    no attachment test             33 of 44
    - the speaker outranks         30    3 removed, 0 collateral
    - a recipient is not an owner  28    2 removed, 0 collateral
    - a later named subject severs 26    2 removed, 0 collateral
    - a first-person clause severs 24    2 removed, 0 collateral
    - a relative clause is not an owner 22  2 removed, 0 collateral

Then RECALL, which the five corrections above say nothing about. 421
clauses name a colleague and a day without matching `<Name> <obligation
verb>`, and reading them found the verb this firm delegates with:

    + `owns`                       31    9 added, all of them clean
    + an adverb may follow the name 33    2 added, both clean
    + `committed`                  35    1 added, clean

`owned` and `takes` were measured beside them and add nothing at all.

Bare `needs` was measured and REJECTED. It looks like the others and is
not: "Dov needs it locked before Friday" makes Dov the party who WANTS it,
not the one who owes it, where "needs to" keeps the obligation with the
subject. One row, and only reading it separates the two senses.

    + the possessive form          39    5 added, 4 of them clean
    + `circulates`, guarded        41    2 added, both clean

The possessive was the one recall gap that behaved like a PRECISION
problem, and getting it in took three attempts:

    raw                                13 additions, ~54%
    + no questions, no gating words     7 additions, ~71%
    + the day is not the subject        5 additions, 4 of 5

71% was better than 54% and still below the ratio the rule already had,
which is the distinction that mattered: an improvement can be real and
insufficient at the same time. The third condition -- "Thursday morning is
our call" identifies a day rather than assigning one -- is what made the
form worth admitting.

The one row of five that is arguably wrong is "Jamal's discovery response
... is logged closed, due 1/24 Tuesday", an item already finished. A
fourth guard for `closed`/`done` would take it, and one row is not enough
to justify a condition, so it stays.

**Two measured negatives, kept because they cost nothing to record and
would otherwise be re-derived.**

The VOCATIVE form -- "Hyun-woo, opposition brief is due Friday" -- is
real and not admitted. Raw it adds 75 rows, nearly all of them address
plus a meeting slot ("Dov, Thursday, 2:00pm, 20 minutes"). Requiring an
explicit `due` leaves exactly 2, and one of those is "Hyun-woo, The
opposition brief WAS due Friday" -- a report of a missed deadline, which
the brief already excludes. One clean row on 45 days does not justify a
fourth path.

PAST TENSE is not a defect in either rule. The brief excludes "a turn
reporting that something was done on a day", and a keyword scan flags 8 of
the first-person rule's 165 merrick rows and 1 of these 41. Reading all
nine: every one is a genuine future commitment where `filed`, `closed` or
`circulated` is a participle describing the DELIVERABLE's state -- "I'll
have it filed by Friday", "I'll have the review closed out before end of
day". The scan finds the word and not the tense.

**Run outside its own corpus, the two routes stop agreeing, and that
number is the honest measure of how much the dev set flatters them.**

    delegation epoch (45d)   1 318 items   41 assignments   0 disagreements
    merrick meetings         2 872 items   15              1
    merrick mail             1 399 items    2              0
    calder mail              3 048 items   15              0
    ashgrove mail              354 items   20              4

All five disagreements localise to ONE question -- whether a first-person
clause standing BEFORE the colleague severs the assignment -- and the two
routes are each right about half of it:

    "I note that Sylvia has ringfenced the Wednesday GL sync"
        the word route refuses. Correct: a named sync, not a deadline.
    "I have received confirmation that Imogen will provide the specific
     engagement list by end of day today"
        the word route refuses. Wrong: that is exactly an assignment,
        reported rather than made.

The regex route asks whether an `I'll`/`I will` PROMISE precedes, which is
too narrow; the word route asks whether any first-person verb precedes,
which is too broad. What separates the cases looks like a reporting FRAME
-- "I have received confirmation that", "I note that" -- from the speaker
taking the work themselves.

**That hypothesis was tested against 104 cases and it fails.** Gathering
every clause across four corpora where a first-person verb stands before a
colleague and a day:

    104 occurrences, 40 distinct first-person verbs
     73  no `that` at all
     22  the colleague appears possessively
      9  a `that` intervenes -- and it is mostly the DEMONSTRATIVE:
         "I can turn THAT comparison around by tomorrow once Klara's
         timeline is in"

So the complementiser test does not separate them, and neither does the
verb: `can`, `have`, `need`, `want` and `should` account for half the
occurrences and appear on both sides. The distinction is semantic and this
corpus does not mark it lexically.

**The resolution is therefore a bright line, not a better pattern.** The
first-person rule faced the same wall on attachment and answered it by
stating a narrow, checkable rule in the brief and accepting the semantic
misses: a day is attached by these prepositions or it ends the clause,
full stop. This family needs the equivalent -- a stated rule about what a
first-person clause before a colleague does -- chosen for gradability
rather than for being right about all 104. Which line to draw is a
measurement to run when the task is built, not a guess to make now.

Worth recording separately: **ashgrove carries 20 assignments in 354
mails**, the densest of any corpus measured, against 41 in 1,318 for the
world built specifically to produce them. A world spec was not the only
way to get this family after all.

**Status: a dev artifact, not a shipped rule.** It is developed against
`out/delegation-epoch` (45 days) and has no second derivation, no oracle
and no task. `promise_rule` reached its present precision over fourteen
corrections, every one adjudicated by readers who never saw the code, and
this has had three. It is committed at this stage because the three are
measured and the next reader should start from them rather than from the
subject-swap that does not work.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _promise_rule():
    """The shared machinery, loaded rather than copied.

    Clause splitting, the deadline table, negation, conditions and
    supersession are about English and about this firm's calendar, not
    about who is speaking. Only attachment and the owner form differ, and
    those are stated here.
    """

    spec = importlib.util.spec_from_file_location(
        "_assignment_promise_rule", _HERE / "promise_rule.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def roster(state: Path) -> dict[str, str]:
    """First name -> full name, from the world's own people table."""

    database = state / "meetings.db"
    if not database.is_file():
        database = state / "gmail.db"
    connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
    return {
        name.split()[0]: name
        for _person, name in connection.execute("SELECT person_id, name FROM people")
    }


# The verbs that put an obligation on somebody else. `owes` and `will` are
# unambiguous; `has` and `is` carry most of the volume and most of the
# trouble -- "Ingrid has lender consent due Wednesday" is an obligation and
# "once Mira has a name" is not, which is what the conditions below are
# for.
# `owns` is the word this firm actually delegates with -- "Hyun-woo owns
# it, due Friday", "Dov owns it, Wed EOD", "Rosalie owns the linkage fix by
# EOD tomorrow". It was missing because the verb list came from the 10-day
# probe, where it never appeared; adding it lifts 22 assignments to 31 and
# every one of the nine is clean.
#
# `owned` and `takes` were tried alongside it and add NOTHING -- 31 either
# way -- so they are not here. A verb that decides no verdict is a
# condition the brief would have to state and the corpus never exercises.
OBLIGATION = r"owes|owns|will|'ll|has|is|needs to|committed"

# A colleague named just after one of these is receiving the work, not
# owing it: "Hyun-woo's draft to Bennett", "Mira owes Elena and Ingrid
# firm dates". Two rows in 44 turned on this.
_RECIPIENT = re.compile(r"\b(?:to|for|with|and)\s+$", re.IGNORECASE)


# A first-person clause standing between the assignee and the day takes
# the day with it: "Cecile has confirmed the invoice ... and I'm personally
# holding the team to end of day today" is the SPEAKER's end of day.
#
# Written as verb forms rather than as a bare `I`, and the difference cost
# a row before it was caught. `\bI\b` matches the `I` in "Samir has
# Sub-Fund I cert by EOD Thursday" -- a designation, not a pronoun -- and
# silently dropped a sound assignment. The removals have to be read, not
# counted: the count went 26 -> 23 and looked like a better correction than
# the one that goes 26 -> 24.
_FIRST_PERSON = re.compile(
    r"\bI'(?:m|ve|ll|d)\b"
    r"|\bI\s+(?:am|will|have|want|need|can|could|would|should|do|did|expect"
    r"|think|hold|prefer)\b"
    r"|\bwe'(?:re|ve|ll)\b"
    r"|\bwe\s+(?:are|will|have|can|should|need)\b",
    re.IGNORECASE,
)


def _new_subject(roster_pattern: str) -> re.Pattern:
    """A different colleague, after a comma, taking the day with them.

    "Saoirse has the analysis to Dov today, Mira's holding Wed EOD firm"
    gives Saoirse a Wednesday she was never given. `promise_rule`'s own
    `_ELSEWHERE` misses this because it wants a connective and a comma is
    not one.
    """

    return re.compile(rf",\s+(?:{roster_pattern})\b(?:'s)?\s+\w", re.IGNORECASE)


# Words that can open a clause. A colleague named right after any OTHER
# lowercase word is inside a relative clause modifying that word rather
# than being assigned anything: "the general IP schedule item Mira is
# tracking for Wednesday EOD" gives Mira a Wednesday that belongs to the
# item. Two rows in 44.
_CLAUSE_OPENERS = frozenset(
    (
        "and",
        "or",
        "but",
        "so",
        "then",
        "that",
        "which",
        "because",
        "if",
        "once",
        "when",
        "while",
        "unless",
        "with",
        "separately",
        "also",
        "plus",
    )
)


def _inside_a_relative_clause(clause: str, at: int) -> bool:
    """Whether the colleague at `at` is modifying a noun rather than owning."""

    before = clause[:at].rstrip()
    if not before:
        return False
    if before[-1] in ",;:\u2014\u2013-":
        return False
    words = re.findall(r"[\w'-]+", before)
    return (
        bool(words)
        and words[-1].lower() not in _CLAUSE_OPENERS
        and (words[-1][:1].islower())
    )


# The possessive form: "Hyun-woo's draft is due to me by midday tomorrow".
# Real, common, and the one recall gap that behaves like a precision
# problem -- raw it adds 13 rows at about 54%, because the day so often
# belongs to something named later. Three conditions of its own bring it
# to five rows at four-of-five, which is where the rest of the rule sits:
#
#   a question is not an assignment    "is Wed EOD still holding?"
#   a gate anywhere before the day     "once Elena's answer lands EOD"
#   the day is not the SUBJECT         "Thursday morning is our call"
#
# Two guards borrowed from elsewhere got it to 71% and that was NOT enough
# -- better than before and still below the rule's own ratio, which are
# different things. The third condition is what made it worth adding.
_POSSESSIVE_LINK = re.compile(
    r"\b(?:is due|are due|due|is|goes|lands|comes)\b", re.IGNORECASE
)
_GATE = re.compile(
    r"\b(?:once|gated on|depends on|waiting on|pending|blocker)\b", re.IGNORECASE
)
_DAY_IS_SUBJECT = re.compile(
    r"^\s*(?:morning|afternoon|evening|EOD)?\s*(?:is|was|are)\b", re.IGNORECASE
)


def _possessive_assignment(clause: str, who: str, names: dict[str, str], rule):
    """ "<Name>'s <deliverable> ... due <day>", with its own three conditions."""

    if "?" in clause:
        return None
    for owner in re.finditer(rf"\b({who})'s\b", clause):
        mine = rule._OWNER.search(clause)
        if mine and mine.start() < owner.start():
            continue
        if _RECIPIENT.search(clause[max(0, owner.start() - 6) : owner.start()]):
            continue
        # NOT `_inside_a_relative_clause`, and that is deliberate. It reads a
        # lowercase word before the name as evidence of modification, which
        # is right for the bare-name form ("the item Mira is tracking") and
        # wrong for a possessive: "That timeline ASSUMES Cecile's III.B
        # lands by early Friday" has a verb before the name introducing a
        # clause subject, and the check costs that row.
        for pattern, token in rule._DEADLINE:
            for found in pattern.finditer(clause):
                start, end = found.start(), found.end()
                tail = clause[end:]
                if start < owner.end():
                    continue
                if rule._RULED_OUT.search(clause[max(0, start - 24) : start]):
                    continue
                if not rule._BINDING.match(tail) and (
                    rule._ALTERNATIVE_BEFORE.search(clause[owner.end() : start])
                    or rule._ALTERNATIVE_AFTER.match(tail)
                ):
                    continue
                span = clause[owner.end() : start]
                if not _POSSESSIVE_LINK.search(span):
                    continue
                if _GATE.search(clause[:start]) or _DAY_IS_SUBJECT.match(tail):
                    continue
                if _new_subject(who).search(span) or _FIRST_PERSON.search(span):
                    continue
                if not rule._BINDING.match(tail) and rule._CONDITION.search(span):
                    continue
                if rule._negated(span):
                    continue
                if rule._ELSEWHERE.search(span) or rule._PRONOUN_SUBJECT.search(span):
                    continue
                return names.get(owner.group(1), owner.group(1)), token
    return None


# A bare present-tense delivery verb -- "Gideon circulates finalized
# language tomorrow morning" -- states an assignment without any of the
# obligation words. It needs the possessive path's guards, because most
# occurrences are gated ("once Gideon circulates tomorrow, ...") or are
# questions, and it CANNOT share them with the obligation path: applying
# the gate check there costs a sound row, "pending the release redlines,
# which Cecile has to Roland by end of day", where `pending` describes the
# footnote and not Cecile's deadline.
#
# `sends` and `delivers` were measured beside `circulates` and add nothing
# once the guards are on. `gets` was measured and REJECTED -- "Imelda gets
# the updated fee estimate by EOD tomorrow" makes Imelda the recipient,
# the same inversion as bare `needs`.
_PRESENT_TENSE = r"circulates"


def _present_tense_assignment(clause: str, who: str, names: dict[str, str], rule):
    """A present-tense delivery verb, under the guards it needs."""

    if "?" in clause:
        return None
    owner_form = re.compile(
        rf"\b({who})\b(?:\s+(?:still|already|now|then|also|[a-z]+ly))?"
        rf"\s+(?:{_PRESENT_TENSE})\b"
    )
    for owner in owner_form.finditer(clause):
        mine = rule._OWNER.search(clause)
        if mine and mine.start() < owner.start():
            continue
        if _RECIPIENT.search(clause[max(0, owner.start() - 6) : owner.start()]):
            continue
        if _inside_a_relative_clause(clause, owner.start()):
            continue
        for pattern, token in rule._DEADLINE:
            for found in pattern.finditer(clause):
                start, end = found.start(), found.end()
                tail = clause[end:]
                if _GATE.search(clause[:start]) or start < owner.end():
                    continue
                if _DAY_IS_SUBJECT.match(tail):
                    continue
                if rule._RULED_OUT.search(clause[max(0, start - 24) : start]):
                    continue
                if not rule._BINDING.match(tail) and (
                    rule._ALTERNATIVE_BEFORE.search(clause[owner.end() : start])
                    or rule._ALTERNATIVE_AFTER.match(tail)
                ):
                    continue
                span = clause[owner.end() : start]
                if _new_subject(who).search(span) or _FIRST_PERSON.search(span):
                    continue
                if not rule._BINDING.match(tail) and rule._CONDITION.search(span):
                    continue
                if rule._negated(span):
                    continue
                if rule._ELSEWHERE.search(span) or rule._PRONOUN_SUBJECT.search(span):
                    continue
                return names.get(owner.group(1), owner.group(1)), token
    return None


def assignment_in(text: str, names: dict[str, str]) -> tuple[str, str] | None:
    """The colleague and the deadline token this turn assigns, or None."""

    rule = _promise_rule()
    who = (
        "(?:"
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + ")"
    )
    # An adverb may stand between the colleague and the verb: "Jamal STILL
    # owes confirmation ... due next Tuesday", "Dov STILL owes Elena's side
    # the actual IP schedule, targeted for Wed EOD". Two rows, both clean.
    owner_form = re.compile(
        rf"\b({who})\b(?:\s+(?:still|already|now|then|also|[a-z]+ly))?"
        rf"\s+(?:{OBLIGATION})\b"
    )
    new_subject = _new_subject(who)

    for clause in rule._CLAUSE.split(text or ""):
        for owner in owner_form.finditer(clause):
            # The speaker outranks: a first-person promise earlier in the
            # clause makes any later colleague a purpose clause, not an
            # assignee. "I'll pull it together today so Fionnuala has them
            # ahead of 9:30 tomorrow" is the speaker's own promise.
            mine = rule._OWNER.search(clause)
            if mine and mine.start() < owner.start():
                continue
            if _RECIPIENT.search(clause[max(0, owner.start() - 6) : owner.start()]):
                continue
            if _inside_a_relative_clause(clause, owner.start()):
                continue
            for pattern, token in rule._DEADLINE:
                for found in pattern.finditer(clause):
                    start, end = found.start(), found.end()
                    tail = clause[end:]
                    binding = rule._BINDING.match(tail) is not None
                    if rule._RULED_OUT.search(clause[max(0, start - 24) : start]):
                        continue
                    if start < owner.end():
                        continue
                    span = clause[owner.end() : start]
                    if new_subject.search(span) or _FIRST_PERSON.search(span):
                        continue
                    if not binding and rule._CONDITION.search(span):
                        continue
                    if rule._negated(span):
                        continue
                    if not binding and (
                        rule._ALTERNATIVE_BEFORE.search(span)
                        or rule._ALTERNATIVE_AFTER.match(tail)
                    ):
                        continue
                    if rule._ELSEWHERE.search(span) or rule._PRONOUN_SUBJECT.search(
                        span
                    ):
                        continue
                    return names.get(owner.group(1), owner.group(1)), token

    # ...then the two forms the verb pattern cannot see, each under its own
    # guards. Order does not matter here: they are disjoint by construction,
    # one keying on `<Name>'s` and the other on a present-tense verb.
    for clause in rule._CLAUSE.split(text or ""):
        found = _possessive_assignment(clause, who, names, rule)
        if found:
            return found
    for clause in rule._CLAUSE.split(text or ""):
        found = _present_tense_assignment(clause, who, names, rule)
        if found:
            return found
    return None
