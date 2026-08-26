"""Second derivation of the assignment rule, walking words.

`assignment_rule` finds a colleague and a day with patterns over
characters. This walks tokens and asks the same questions in a different
order. The two agreeing is worth something only because neither can see
the other's mistakes; the first-person pair earned that claim by
disagreeing on exactly one turn in 4,271 -- "I'll plan to check in with
you by end of week", where one route read `with you` as a new subject --
and that was a real defect in a change already believed correct.

The assignment rule has had fifteen edits today and no second opinion at
all. This is the second opinion.

**Independence is at the level of assumptions, not code.** Sharing nothing
textual is not enough: an earlier pair in this dataset shared no code,
encoded the same too-narrow negation, agreed on every utterance, and
eleven of twenty rows were wrong. So the questions here are asked
differently on purpose --

    the regex route          this route
    ---------------          ----------
    a pattern over the       a scan over tokens with the
    clause's characters      colleague's index known
    lookbehind for a         walk back over words and ask
    recipient preposition    what stands there
    `,\\s+<Name>` for a       find the comma, then look at the
    second subject           next token
"""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path

_HERE = Path(__file__).resolve().parent


def _rules():
    """The shared promise machinery and the regex assignment route."""

    out = []
    for name in ("promise_rule", "assignment_rule"):
        spec = importlib.util.spec_from_file_location(
            f"_check_{name}", _HERE / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        out.append(module)
    return out[0], out[1]


# Kept as words rather than as a pattern, and read by index.
# `needs` is NOT here on its own. The regex route admits "needs to" and
# refuses bare "needs", because "Dov needs it locked before Friday" makes
# Dov the party who wants it. Writing this list from memory I put `needs`
# in, and the comparison caught it on that exact sentence -- which is what
# a second derivation is for, and it found the fault in ITSELF rather than
# in the rule it checks.
# No `circulates`: the regex route puts it on a GUARDED path of its own,
# because most occurrences are `once`-gated. Carrying it here without the
# guard made this route admit "same-day once Gideon circulates tomorrow",
# which that route refuses -- a difference in the CHECK, read at first as a
# difference in the rule.
_OBLIGATION = frozenset(("owes", "owns", "will", "ll", "has", "is", "committed"))
_NEEDS_TO = ("needs", "to")
_ADVERBS = frozenset(("still", "already", "now", "then", "also"))
_RECEIVING = frozenset(("to", "for", "with", "and"))
# The contracted forms are here because keeping apostrophes in the
# tokeniser -- needed so `Hyun-woo` survives -- turned `I'll` into `i'll`,
# which is not `i`. One fix broke another check, and the comparison caught
# it as three rows the word route admitted and the regex route refused.
_SPEAKER = frozenset(
    ("i", "we", "i'll", "i'm", "i've", "i'd", "we'll", "we're", "we've")
)

# Words that can open a clause. A colleague standing right after any OTHER
# ordinary word is inside a relative clause modifying it -- "the general IP
# schedule item Mira is already tracking for Wednesday EOD" -- and owes
# nothing. The regex route finds this by looking at the character before;
# this one asks what the previous TOKEN is, which is the same question
# reached from the other side.
_OPENERS = frozenset(
    (
        ",",
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


# The promise rule's own owner forms, as this route's tokeniser sees them.
#
# `_words` KEEPS apostrophes -- changed hours ago so `Hyun-woo` survives --
# so `I'll` arrives as the single token `i'll`, not the pair (i, ll). The
# first version of this constant was written from a comment that was true
# before that change, matched nothing, and let six rows through. A stale
# note about my own tokeniser, in a file whose subject is stale notes.
# Both spellings AND both tokenisations. `_words` keeps the straight
# apostrophe and splits on the curly one, so `I'll` is one token and
# `I\u2019ll` is two -- which the tokeniser check printed plainly the moment
# it was asked, and which neither the code nor its comment had noticed.
_PROMISE_SINGLE = frozenset(("i'll",))
_PROMISE_PAIR = (("i", "will"), ("i", "ll"))


def _words(text: str) -> list[str]:
    """Tokens, keeping commas AND hyphens.

    The hyphen matters and its absence hid a whole class: splitting on
    every non-word character turns `Hyun-woo` into `hyun` and `woo`,
    neither of which is a roster name, so every row belonging to the
    firm's hyphenated colleagues was invisible here -- and the comparison
    read that silence as agreement.
    """

    return [w.casefold() for w in re.split(r"([,])|[^\w,'-]+", text or "") if w]


# Verbs that mark the preceding pronoun as a real subject.
_AFTER_SUBJECT = frozenset(
    (
        "am",
        "will",
        "have",
        "want",
        "need",
        "can",
        "could",
        "would",
        "should",
        "do",
        "did",
        "expect",
        "think",
        "hold",
        "prefer",
        "are",
    )
)


def _is_speaker(words: list[str], at: int) -> bool:
    """Whether the token at `at` is the speaker acting, not a stray letter."""

    word = words[at]
    if word in ("i", "we"):
        return at + 1 < len(words) and words[at + 1] in _AFTER_SUBJECT
    return word in _SPEAKER


# The two forms the obligation-verb path cannot see, mirrored from the
# regex route. Their guards are theirs alone: applying the gate check to
# the obligation path costs a sound row there, which is measured.
_POSSESSIVE_LINK = re.compile(
    r"\b(?:is due|are due|due|is|goes|lands|comes)\b", re.IGNORECASE
)
_GATE = re.compile(
    r"\b(?:once|gated on|depends on|waiting on|pending|blocker)\b", re.IGNORECASE
)
_DAY_IS_SUBJECT = re.compile(
    r"^\s*(?:morning|afternoon|evening|EOD)?\s*(?:is|was|are)\b", re.IGNORECASE
)
_PRESENT_TENSE = frozenset(("circulates",))


def _tail_after(clause: str, words: list[str], at: int) -> str | None:
    """The clause text following the token at index `at`.

    Walks the words in order and consumes each from the front of the
    remaining text, so the offset is the token's, not the first place its
    letters happen to appear.
    """

    rest = clause
    for word in words[: at + 1]:
        if word == ",":
            _before, sep, rest = rest.partition(",")
            if not sep:
                return None
            continue
        found = re.search(re.escape(word), rest, re.IGNORECASE)
        if not found:
            return None
        rest = rest[found.end() :]
    return rest


def _day_token(promise, text: str) -> str | None:
    """The deadline the tail names, under every condition BUT attachment.

    The deadline table, the negation rule and the trigger words are shared
    with the promise rule deliberately: they are facts about English and
    about this firm's calendar, and two copies of them would be two things
    to drift. What is NOT shared is how the owner and the conditions around
    them are found, which is where a second opinion is worth having.
    """

    for pattern, token in promise._DEADLINE:
        for found in pattern.finditer(text or ""):
            start, end = found.start(), found.end()
            tail = text[end:]
            binding = promise._BINDING.match(tail) is not None
            span = text[:start]
            if promise._RULED_OUT.search(text[max(0, start - 24) : start]):
                continue
            if not binding and promise._CONDITION.search(span):
                continue
            if promise._negated(span):
                continue
            if not binding and (
                promise._ALTERNATIVE_BEFORE.search(span)
                or promise._ALTERNATIVE_AFTER.match(tail)
            ):
                continue
            if promise._ELSEWHERE.search(span) or promise._PRONOUN_SUBJECT.search(span):
                continue
            return token
    return None


def _day_span(promise, text: str) -> tuple[int, int]:
    """Start and END of the first admitted deadline form, or (len, len)."""

    best = None
    for pattern, _token in promise._DEADLINE:
        found = pattern.search(text or "")
        if found and (best is None or found.start() < best[0]):
            best = (found.start(), found.end())
    return best if best is not None else (len(text or ""), len(text or ""))


def _day_at(promise, text: str) -> int:
    """Character offset of the first admitted deadline form, or the end."""

    return _day_span(promise, text)[0]


def assignment_in(text: str, names: dict[str, str]) -> tuple[str, str] | None:
    """The colleague and deadline token this turn assigns, or None.

    Covers all three of the regex route's paths: an obligation verb, a
    possessive subject, and a present-tense delivery verb. It covered only
    the first at first, and the comparison duly reported seven rows as
    "regex-only" -- true, and indistinguishable at a glance from seven
    rows where the two disagree. Abstention has to be finished, not
    annotated.
    """

    promise, _assignment = _rules()
    first = {short.casefold(): full for short, full in names.items()}

    for clause in promise._CLAUSE.split(text or ""):
        words = _words(clause)
        for index, word in enumerate(words):
            if word not in first:
                continue
            # the verb, possibly after one adverb
            at = index + 1
            if at < len(words) and words[at] in _ADVERBS:
                at += 1
            if at >= len(words) or (
                words[at] not in _OBLIGATION and tuple(words[at : at + 2]) != _NEEDS_TO
            ):
                continue
            # a colleague introduced by one of these is receiving, not owing
            if index > 0 and words[index - 1] in _RECEIVING:
                continue
            # ...or modifying the noun before them rather than owning
            if index > 0 and words[index - 1] not in _OPENERS:
                continue
            # The speaker's own PROMISE, earlier in the clause, governs it.
            #
            # A promise -- `I'll` / `I will` -- and not any first-person
            # verb. This route asked the broader question and the two
            # disagreed five times across two corpora, in both directions:
            #
            #   "I have received confirmation that Imogen will provide the
            #    specific engagement list by end of day today"
            #       the broad test refuses. Wrong: that IS an assignment,
            #       reported rather than made.
            #   "the clarity Sylvia has provided on the investigation path"
            #       the broad test refuses. Right.
            #
            # There is no brief for this family yet, so nothing decides it
            # from outside -- unlike the promise rule, where consulting the
            # brief settled the equivalent question in a minute. This is a
            # design choice, made narrow for consistency with the promise
            # rule's own owner form, and recorded as a choice.
            if any(
                words[s] in _PROMISE_SINGLE or tuple(words[s : s + 2]) in _PROMISE_PAIR
                for s in range(index)
            ):
                continue
            # The day, found in the ORIGINAL text rather than in rejoined
            # tokens. Rejoining drops the punctuation the clause rule
            # needs, and this route was abstaining on 23 rows because of
            # it -- silence the comparison reported as agreement.
            # Locate the verb by POSITION. `clause.partition(verb)` finds
            # the first substring match, which for a short token like `is`
            # can land inside an earlier word and hand back the wrong tail.
            after = _tail_after(clause, words, at)
            if after is None:
                continue
            # NOT `commitment_in`: that applies the attachment test, which
            # the assignment rule drops on purpose because this idiom
            # attaches by bare apposition -- "Samir has cap table recon to
            # Elena EOD tomorrow". Calling it made this route abstain on
            # thirteen sound rows, and the comparison read the silence as
            # agreement rather than as a hole.
            token = _day_token(promise, after)
            if not token:
                continue
            # A second named colleague after a comma takes the day, but
            # only when they stand BEFORE it. "Samir has the cert by EOD
            # Thursday, Elena files blue sky Friday" has Elena after the
            # day, and scanning the whole tail rejected Samir's own row.
            before_day = _words(after[: _day_at(promise, after)])
            # A first-person clause standing between the colleague and the
            # day takes the day with it: "Hyun-woo has the pen, but I'M
            # supervising and I WANT his draft on my desk by Wednesday".
            #
            # A BARE `i` is not enough, and this route rediscovered why on
            # its own. "Samir has Sub-Fund I cert by EOD Thursday" has a
            # Roman numeral, not a pronoun, and treating it as one refused
            # sixteen sound rows here -- the identical trap the regex route
            # fell into this morning with `\bI\b`. Two derivations, the
            # same mistake, hours apart: the ambiguity is in the corpus,
            # not in either implementation.
            if any(_is_speaker(before_day, step) for step in range(len(before_day))):
                continue
            # `mira's` is Mira. Without stripping the possessive the sever
            # check missed ", Mira's holding Wed EOD firm" entirely.
            if any(
                before_day[step] == ","
                and step + 1 < len(before_day)
                and before_day[step + 1].removesuffix("'s") in first
                for step in range(len(before_day))
            ):
                continue
            return first[word], token

    # The possessive: "<Name>'s <deliverable> ... due <day>", under the
    # three conditions the regex route gives it.
    for clause in promise._CLAUSE.split(text or ""):
        if "?" in clause:
            continue
        words = _words(clause)
        for index, word in enumerate(words):
            stem = word.removesuffix("'s")
            if stem == word or stem not in first:
                continue
            if index > 0 and words[index - 1] in _RECEIVING:
                continue
            if any(
                words[s] in _PROMISE_SINGLE or tuple(words[s : s + 2]) in _PROMISE_PAIR
                for s in range(index)
            ):
                continue
            after = _tail_after(clause, words, index)
            if after is None:
                continue
            token = _day_token(promise, after)
            if not token:
                continue
            at, ends = _day_span(promise, after)
            # The linking verb has to stand BEFORE the day, not anywhere in
            # the tail. Searching the whole tail let "Mira's holding Wed EOD
            # firm on the IP schedule escalation" qualify on an `is` that
            # appears later in the sentence, and admitted seven rows the
            # other route refuses.
            if not _POSSESSIVE_LINK.search(after[:at]):
                continue
            if _GATE.search(clause[: len(clause) - len(after) + at]):
                continue
            # Read from the END of the day form: "Thursday morning IS our
            # call" identifies a day rather than assigning one, and reading
            # from the start answers a different question.
            if _DAY_IS_SUBJECT.match(after[ends:]):
                continue
            before = _words(after[:at])
            # A first-person clause between the colleague and the day takes
            # the day: "Fionnuala's manager script is right and I'LL want it
            # nailed down Thursday" is the speaker's Thursday.
            if any(_is_speaker(before, step) for step in range(len(before))):
                continue
            if any(
                before[step] == ","
                and step + 1 < len(before)
                and before[step + 1].removesuffix("'s") in first
                for step in range(len(before))
            ):
                continue
            return first[stem], token

    # The present-tense delivery verb, under the same guards.
    for clause in promise._CLAUSE.split(text or ""):
        if "?" in clause:
            continue
        words = _words(clause)
        for index, word in enumerate(words):
            if word not in first:
                continue
            at = index + 1
            if at < len(words) and words[at] in _ADVERBS:
                at += 1
            if at >= len(words) or words[at] not in _PRESENT_TENSE:
                continue
            if index > 0 and (
                words[index - 1] in _RECEIVING or words[index - 1] not in _OPENERS
            ):
                continue
            if any(
                words[s] in _PROMISE_SINGLE or tuple(words[s : s + 2]) in _PROMISE_PAIR
                for s in range(index)
            ):
                continue
            after = _tail_after(clause, words, at)
            if after is None:
                continue
            token = _day_token(promise, after)
            if not token:
                continue
            if _GATE.search(
                clause[: len(clause) - len(after) + _day_at(promise, after)]
            ):
                continue
            return first[word], token
    return None
