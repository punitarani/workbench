"""A second opinion on what the speaker says they are stuck on.

Written from the brief, never from `blocked_rule`. Copying that rule's
expression reproduces its bug and then certifies that the two agree, which
is how two published scores in this tree turned out to be the answer key.

The independence is at the level of ASSUMPTIONS, not code:

  * that rule finds the complaint with one regex spanning subject and
    predicate together; this walks WORDS, locating the subject and the
    stuck phrase separately and asking what lies between them;
  * that rule bounds the gap in CHARACTERS (60); this bounds it in WORDS
    (12), so a bound wrong on one side shows up as a disagreement rather
    than being shared. Those two numbers were set independently against the
    corpus and are not conversions of each other;
  * that rule tests negation over the matched span; this tests it over the
    tokens strictly between subject and predicate.

A rule and its checker in this tree once agreed across 10,211 items in six
corpora while both were wrong in four ways, because both were written from
the same brief and under-implemented the same clause. Different routes to
the same sentence are the only defence that has worked.
"""

from __future__ import annotations

import re

# Words, with apostrophes kept: `I'm` and `we're` are single tokens whose
# apostrophe is what marks the subject. Splitting on it would turn `we're`
# into `we` + `re` and lose the contraction the new-subject test needs.
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")

# Contracted first-person forms are single tokens here, because the
# tokeniser keeps apostrophes -- so `i've` is not `i`, and a set holding
# only `i` cannot see "I'VE got a related privilege-flag memo waiting on
# ownership clarity from Noor". Two of five remaining disagreements.
_SPEAKER = frozenset(
    ("i", "i'm", "i've", "i'll", "i'd", "my", "mine")
)
_OTHERS = frozenset(
    ("we", "we're", "we’re", "they", "they're", "they’re", "you", "you're",
     "you’re", "he", "he's", "he’s", "she", "she's", "she’s")
)
_JOINERS = frozenset(("and", "so", "but", "then", "while"))
# Contracted negations spelled out. `isn't`, `don't`, `haven't` are single
# tokens here -- the tokeniser keeps apostrophes -- so a test for "not"
# does not see them, and "imelda's runway ISN'T waiting on anything" read
# as the speaker being stuck.
_REFUSALS = frozenset(
    ("no", "not", "never", "rather", "instead", "without", "stopped", "done",
     "isn't", "aren't", "wasn't", "weren't", "don't", "doesn't", "didn't",
     "won't", "haven't", "hasn't", "hadn't")
)

# The stuck phrases, as word sequences rather than as alternation. A phrase
# of several words is a contiguous-subsequence test, which is what "said
# plainly" means once the text is tokens.
_STUCK = (
    ("blocked", "on"),
    ("waiting", "on"),
    ("waiting", "for"),
    ("held", "up", "by"),
    ("stuck", "on"),
    ("can't", "move"),
    ("can't", "proceed"),
    ("can't", "close"),
    ("can't", "sign"),
    ("can't", "finish"),
    ("cant", "move"),
    ("cant", "proceed"),
    ("cant", "close"),
    ("cant", "sign"),
    ("cant", "finish"),
)

# How many words may stand between the speaker and the complaint. Set
# against the corpus independently of the other route's character bound --
# 12 words is what the true positives need, and the two numbers agreeing in
# effect is evidence rather than a shared assumption.
_GAP = 12

_ENDS = re.compile(r"(?<=[.?!;:])\s+|\s*[—–]\s*|\s+-\s+")


def _words(text: str) -> list[str]:
    return [w.casefold().replace("’", "'") for w in _WORD.findall(text or "")]


def _stuck_at(words: list[str], start: int) -> int | None:
    """Index where a stuck phrase begins at or after `start`, or None."""

    for index in range(start, len(words)):
        for phrase in _STUCK:
            if tuple(words[index : index + len(phrase)]) == phrase:
                return index
    return None


def blocked_in(text: str, names=()) -> bool:
    """Whether this turn reports the speaker as stuck on something."""

    others = {n.casefold() for n in names}

    for clause in _ENDS.split(text or ""):
        if clause.rstrip().endswith("?"):
            continue
        words = _words(clause)
        for at, word in enumerate(words):
            if word not in _SPEAKER:
                continue
            found = _stuck_at(words, at + 1)
            if found is None or found - at > _GAP:
                continue
            between = words[at + 1 : found]
            if any(w in _REFUSALS for w in between):
                continue
            # A different subject after a joiner owns the complaint: "...on
            # my end, AND WE'RE just waiting on the handbook".
            if any(
                between[i] in _JOINERS and between[i + 1] in _OTHERS
                for i in range(len(between) - 1)
            ):
                continue
            # ...or a NAMED colleague, who the pronoun set cannot cover.
            if any(w.rstrip("'s") in others or w in others for w in between):
                continue
            # ...or any possessive at all. "LITIGATION'S still short the
            # expert fee estimate, waiting on that" is the estimate's wait,
            # not the speaker's, and a thing owns a wait as readily as a
            # person does.
            if any(w.endswith("'s") for w in between):
                continue
            return True
    return False
