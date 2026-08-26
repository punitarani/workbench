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
OBLIGATION = r"owes|will|'ll|has|is|needs to"

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


def assignment_in(text: str, names: dict[str, str]) -> tuple[str, str] | None:
    """The colleague and the deadline token this turn assigns, or None."""

    rule = _promise_rule()
    who = (
        "(?:"
        + "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
        + ")"
    )
    owner_form = re.compile(rf"\b({who})\b\s+(?:{OBLIGATION})\b")
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
    return None
