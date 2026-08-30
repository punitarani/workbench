"""What the speaker says they are stuck on.

The third rule in this family, and the first that is not about a date. The
promise rule reads `I'll ... by Thursday` and asks what the speaker took
on; the assignment rule reads `Mira will ...` and asks what they handed
over. This reads `I'm still waiting on Ulrich` and asks what is not moving.

**Why it needs no deadline.** A commitment without a day cannot be graded —
the register's whole content is the date. A blocker's dates come from the
MEETINGS instead: when it was first said, when it was last said, and how
many rooms in between it was said again. That makes the rule simpler and
the chain harder, because nothing in the sentence tells you where you are
in it. A reader who finds one complaint has no way to know whether it is
the first or the tenth.

**The negation guard is borrowed, not rewritten.** Two of the first ten
matches sampled were "no waiting for round-up" and "escalated to a direct
call rather than waiting on email" -- a refusal to wait and an alternative
chosen INSTEAD of waiting. Both are the promise rule's existing negation
class (`not`, `never`, `n't`, `rather than`, `instead of`), and importing
it is the point: a second copy is a second thing to drift.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

_APOS = "['’]"

# The speaker, or something the speaker owns. `my` earns its place: "the
# reserve analysis in MY memorandum is waiting on that sign-off" is the
# speaker reporting their own work stuck, and it is the commonest form
# after the bare pronoun.
_FIRST_PERSON = rf"(?:\bI\b|\bI{_APOS}m\b|\bI am\b|\bmy\b|\bmine\b)"

# Being stuck, said plainly. Each of these was read in the corpus before it
# was added; none is speculative.
#
# `pending` is NOT here and was measured out. It reads as often as a
# description of a document's state -- "the footnote stays pending" -- as
# it does the speaker's own wait, and separating those needs the whole
# attachment apparatus the promise rule carries for dates. This rule stays
# narrow instead.
_STUCK = (
    r"(?:blocked on|waiting on|waiting for|held up by"
    rf"|can{_APOS}?t (?:move|proceed|close|sign|finish)|stuck on)"
)

# How far the stuck phrase may sit from the first-person subject. Measured:
# 60 characters covers every true positive in the sample and the phrase
# never legitimately sits further, because English puts the complaint next
# to whoever is making it.
_REACH = 60

# The gap is captured so the guards can be asked of it ALONE. Testing them
# over the whole match instead was a bug with a perfectly straight face:
# `_NEGATED` matches `n't`, the stuck phrase `can't close` contains one, so
# every `can't` complaint negated itself and the rule refused all of them.
# Subject and complaint are matched SEPARATELY, and every subject in the
# clause is tried.
#
# One regex spanning both, iterated with `finditer`, cannot do it: matches
# do not overlap, so in "I haven't gotten written confirmation, so I can't
# sign off" the whole sentence is consumed by the first `I` -- rejected for
# the `haven't` in its gap -- and the second `I`, which sits INSIDE that
# match and is the real complaint, is never reached. The count did not move
# when `search` became `finditer`, which is how this surfaced.
_SUBJECT = re.compile(_FIRST_PERSON, re.IGNORECASE)
_COMPLAINT = re.compile(rf"\b{_STUCK}\b", re.IGNORECASE)

# A clause ends where the promise rule says a clause ends. Shared for the
# same reason the negation is: this is a fact about how this firm writes,
# not about what is being extracted.
_CLAUSE = re.compile(r"(?<=[.?!;:])\s+|\s*[—–]\s*|\s+-\s+")

# A different subject standing between the speaker and the complaint. "the
# status memo is done, board disclosure is resolved ON MY END, and WE'RE
# just waiting on the handbook" is the room waiting, not the speaker -- and
# `my` is 40 characters upstream doing nothing but anchoring the match.
#
# The same law the promise rule states as "a conjunction alone does not
# mark this; a new SUBJECT does".
_NEW_SUBJECT = re.compile(
    rf"\b(?:and|so|but|then|while|or)\s+(?:we|they|you|he|she)\b(?:{_APOS}re|\s)",
    re.IGNORECASE,
)


# Any possessive noun standing between the speaker and the complaint takes
# it: "I've got expedited arbitration costed, LITIGATION'S still short the
# expert fee estimate, waiting on that". A named colleague is covered by
# `_somebody_else`; this covers the rest, which are things rather than
# people and just as capable of owning a wait.
_POSSESSED = re.compile(rf"\b[\w-]+{_APOS}s\s+\w", re.IGNORECASE)


def _somebody_else(gap: str, names) -> bool:
    """Whether a NAMED colleague owns the complaint instead of the speaker.

    "I need those three before I'll even think about a mediation date, and
    CECILE'S waiting on the stipulation language too" is Cecile stuck. The
    pronoun test above cannot see it, because the new subject is a name.
    """

    if not names:
        return False
    who = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    return re.search(rf"\b(?:{who})\b(?:{_APOS}s)?\s", gap, re.IGNORECASE) is not None

# The speaker as the OBJECT of the wait rather than its subject. "so
# nothing sits WAITING ON ME" and "the two exceptions are both WAITING ON
# ME, not on anyone else" are the speaker saying they are the holdup --
# the exact inverse of what this register reports, and both were admitted
# because a first-person marker sits a few words upstream doing nothing
# but anchoring the match.
#
# Only the bare pronoun is guarded, and that is a measurement rather than
# caution: `waiting on my <noun>` and `waiting on my end` occur ZERO times
# after a stuck phrase in either corpus, so a guard covering them would
# have no caller. `waiting on my client's approval` is genuinely the
# speaker waiting, and this must not reach it.
_THE_SPEAKER_IS_THE_HOLDUP = re.compile(rf"^\s*(?:me|us)\b", re.IGNORECASE)

# A wait that is OVER. The brief says a blocker is a turn where the speaker
# says they ARE stuck, and "staffing confirmation and the rate-table rows
# have been sitting because I WAS WAITING ON Klara's insurance coverage
# comparison" reports a wait that ended -- the same turn goes on to say "I
# can confirm staffing today". It was the only turn in that person's chain,
# so the whole row was spurious, and every trial of every tier declined it.
#
# Anchored at the END of the gap so it must sit directly against the
# complaint: `was` anywhere upstream would catch unrelated past tense.
#
# `have been` and `has been` are deliberately NOT here. "I've been waiting
# on the filing since Tuesday" is still waiting, and reads as the strongest
# blocker statement this firm makes. `had been` is here for the semantics
# and has zero occurrences in either corpus today; `was`/`were` have one.
_ALREADY_OVER = re.compile(
    r"\b(?:was|were|had been)\s+(?:still\s+|just\s+)?$", re.IGNORECASE
)

# The subject left out. This firm says "Still waiting on Clement." and
# "Waiting on Samir, same as everyone else." far more often than it says
# "I am waiting on Samir", and requiring an explicit pronoun refused
# THIRTY-FOUR turns across the two corpora that every reader takes as the
# speaker reporting themselves stuck. One of them was the turn seven
# trials of three tiers cited as a person's last raise while the key
# stopped their chain ten weeks earlier.
#
# Measured at the ROW level, which is what is graded: admitting these
# leaves the row SET unchanged -- 20 -> 22 on one world, 16 -> 17 on the
# other -- and corrects the ends and the counts of rows that already
# existed. That is the whole of the difference.
# The leading adverbs a dropped subject may hide behind. `separately`
# earns its place by measurement: "Separately, still waiting on a name
# from Elena ... otherwise I'm stuck" is one person's first raise, and
# the key started their chain six days later than five of six trials
# did because of the one word in front.
#
# The comma matters. Without it the set only reaches "still waiting",
# and this firm writes "Separately, still waiting".
_LEADING = r"(?:separately|meanwhile|otherwise|also|still|just|and|so|then)"
_ELIDED = re.compile(rf"^(?:{_LEADING}[,\s]+)*{_STUCK}\b", re.IGNORECASE)

# ...except when the elided phrase is the SUBJECT of the sentence rather
# than a report: "waiting on Bennett before flagging Rosalie JUST
# COMPOUNDS the delay" is advice about what somebody else should do, and
# the wait is hypothetical.
#
# The two conjuncts are both needed and the measurement says so: a gerund
# adjunct ALONE also catches "still waiting on Harriet to send it over,
# and once it lands I'll set up that call BEFORE DRAFTING starts", which
# is a true report. Requiring the clause to name nobody in the first
# person separates them, and across 4,998 turns this rejects exactly the
# one sentence it was written for.
_GERUND_SUBJECT = re.compile(
    r"\b(?:before|after|instead of|without|rather than)\s+\w+ing\b", re.IGNORECASE
)
_ANYONE_FIRST_PERSON = re.compile(
    rf"(?:\bI\b|\bI{_APOS}(?:m|ll|ve|d)\b|\bmy\b|\bmine\b|\bme\b)", re.IGNORECASE
)

# A dropped subject carried across a comma, in a list of predicates that
# all belong to the speaker: "sent within her 2-day deadline, cc'd her and
# adaora, WAITING ON her specific line/share-count numbers". Dov sent it,
# Dov cc'd them, Dov is waiting.
#
# This admits exactly ONE turn in 4,998, and that is stated rather than
# hidden. It was written anyway because two independent readings found it
# without each other: three trials of two tiers reported that person's
# chain starting on the day of this turn, and a judge panel shown only the
# brief and the raw passage -- never this code -- returned WRONG-VALUE on
# the key's row and quoted this sentence. The alternative was to drop the
# row and mark every correct reader wrong for reporting it.
#
# The preceding segment must be a PREDICATE, not a bare participle. That
# distinction is the whole guard and it is worth its length: "the Sable
# Ridge deposition summary, UNSCHEDULED, blocked on the Martinez
# transcript" is the summary that is blocked, not the speaker, and
# `unscheduled` is an adjective sitting against a noun. Requiring the
# segment to head with a verb AND carry complements separates the two --
# 7 turns admitted on the verb test alone, 6 of them the deposition
# summary; 1 with complements required, and it is the right one.
_COORDINATED = re.compile(
    rf",\s*(?:{_LEADING}[,\s]+)*{_STUCK}\b", re.IGNORECASE
)
_A_PREDICATE = re.compile(
    r"^(?:\w+(?:ed|'d|’d)|sent|got|have|had|need|put|left|gave|made|took"
    r"|ran|set|told|asked|added|owe)\b",
    re.IGNORECASE,
)
# Somebody else already holding the floor in this clause. The gap guards
# cannot be reused here: they test what stands between a subject and a
# complaint, and this path has no subject to stand after.
_SOMEBODY_ELSE_LEADS = re.compile(
    rf"\b(?:we|they|you|he|she)\b|\b[\w-]+{_APOS}s\s+\w", re.IGNORECASE
)


def _carried_across_a_comma(clause: str, names) -> bool:
    """Whether a comma-segment complaint belongs to the speaker."""

    found = _COORDINATED.search(clause)
    if found is None:
        return False
    before = clause[: found.start()]
    if _SOMEBODY_ELSE_LEADS.search(before) or _somebody_else(before, names):
        return False
    previous = before.rsplit(",", 1)[-1].strip()
    return bool(_A_PREDICATE.match(previous)) and len(previous.split()) >= 2


_NEGATED = re.compile(
    rf"(?:\bno\b|\bnot\b|\bnever\b|n{_APOS}t\b|\brather than\b|\binstead of\b"
    r"|\bwithout\b|\bstopped\b|\bdone\b)",
    re.IGNORECASE,
)


def roster(state: Path) -> dict[str, str]:
    """First name -> full name, from the world's own people file."""

    rows = sqlite3.connect(f"file:{state / 'clio.db'}?mode=ro", uri=True).execute(
        "SELECT person_id, name FROM people"
    )
    return {name.split()[0]: name for _person, name in rows}


# A subject that carried ACROSS the clause boundary, and still owns the
# wait on the other side of it.
#
# "the Series C disclosure schedule characterization question is partially
# narrowed but not closed - still waiting on written confirmation from
# Ulrich-Bergmann's side" is the QUESTION waiting. The clause splitter
# breaks on " - ", severing "still waiting" from its subject, and the
# elided path then handed it to the speaker.
#
# This is the brief's own rule -- "a thing owns a wait as readily as a
# person does" -- reaching one clause further back than `_POSSESSED` can,
# because `_POSSESSED` looks inside a gap and here there is no gap.
#
# A judge panel found this, against my reading: I had called the row
# correct and the models wrong, and five trials of three tiers had
# answered the same earlier date. They were right.
#
# Two conditions, and both were measured:
#
#   * the break is not a SENTENCE end. Across a full stop the subject does
#     not carry, and "Waiting on Samir, same as everyone else." opening a
#     turn is the speaker;
#   * the copula already HAS its complement. "Status is: still waiting on
#     Clement" is the speaker's status -- the elided clause IS the
#     complement -- where "Sandhurst is the one with a live gap: still
#     waiting on officer names" already said what Sandhurst is, so what
#     follows is a second predicate on the same subject.
#
# Requiring only the first condition drops "Status is:" as well, which is
# wrong. Requiring both changes 2 rows on this world and 0 on the sibling,
# and leaves the row SET unchanged on both.
_A_SUBJECT_ALREADY_STATED = re.compile(
    r"\b(?:is|are|was|were|stays|remains|sits)\b\s+\S+", re.IGNORECASE
)
# Split KEEPING the delimiter: whether the break was a full stop or a dash
# is the whole question, and a splitter that discards it cannot be asked.
_CLAUSE_KEEPING_BREAKS = re.compile(r"((?<=[.?!;:])\s+|\s*[—–]\s*|\s+-\s+)")


def _owned_across_the_break(before: str, clause: str) -> bool:
    """Whether a noun subject stated before the break still owns this wait."""

    if not before or re.search(r"[.?!]\s*$", before):
        return False
    if _ANYONE_FIRST_PERSON.search(clause) or _ANYONE_FIRST_PERSON.search(before):
        return False
    return bool(_A_SUBJECT_ALREADY_STATED.search(before))


def blocked_in(text: str, names=()) -> bool:
    """Whether this turn reports the speaker as stuck on something.

    A boolean and not a span, deliberately. What somebody is waiting FOR is
    free text -- "Ulrich/Cecile to confirm they've started the
    Hargrove/Oseman review" -- and a key component the oracle cannot derive
    is one no agent can be graded on. The register is keyed on WHO and
    WHERE and WHEN, all of which the record states outright.
    """

    pieces = _CLAUSE_KEEPING_BREAKS.split(text or "")
    # pieces alternates segment, delimiter, segment, ...
    for index in range(0, len(pieces), 2):
        clause = pieces[index]
        before = pieces[index - 2] if index >= 2 else ""
        if clause.rstrip().endswith("?"):
            # A question asks whether somebody is stuck; it does not report
            # it. Same carve-out the promise rule makes, for the same
            # reason, and the brief states it.
            continue
        # The subject may be left out entirely, in which case there is no
        # gap to guard and the clause itself is the report.
        lead = _ELIDED.match(clause)
        if (
            lead is not None
            and not _THE_SPEAKER_IS_THE_HOLDUP.match(clause[lead.end() :])
            and not _owned_across_the_break(before, clause)
        ):
            if not (
                _GERUND_SUBJECT.search(clause)
                and not _ANYONE_FIRST_PERSON.search(clause)
            ):
                return True
        if _carried_across_a_comma(clause, names):
            return True
        # EVERY first-person start in the clause, not the first that
        # matches. This firm writes "I haven't gotten written confirmation,
        # so I can't sign off on that schedule yet": the first `I` carries a
        # negation in its gap and is rightly rejected, and abandoning the
        # clause there loses the second `I`, which is the real complaint.
        #
        # The promise rule's docstring has said this from the start --
        # "every owner form in the clause is tried, not only the first" --
        # and this rule was written without it. Four of five remaining
        # disagreements with the second derivation were exactly this.
        for subject in _SUBJECT.finditer(clause):
            complaint = _COMPLAINT.search(clause, subject.end())
            if complaint is None or complaint.start() - subject.end() > _REACH:
                continue
            # The guards are asked of the GAP alone -- what stands between
            # the subject and the complaint. Over the whole match instead,
            # `_NEGATED` sees the `n't` inside `can't close` and every such
            # complaint negates itself.
            gap = clause[subject.end() : complaint.start()]
            if _NEGATED.search(gap) or _NEW_SUBJECT.search(gap):
                continue
            if _ALREADY_OVER.search(gap):
                continue
            if _somebody_else(gap, names) or _POSSESSED.search(gap):
                continue
            # ...and what the complaint points AT, which the gap cannot
            # carry because it ends where the complaint begins.
            if _THE_SPEAKER_IS_THE_HOLDUP.match(clause[complaint.end() :]):
                continue
            return True
    return False
