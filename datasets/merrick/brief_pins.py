"""Pinning a rule so that *any* change to it is visible, not just deletions.

Verifiers in this dataset pin their assumptions with substring tests --
`insists("Cc recipients are not addressees" in brief)`. That catches a rule
being removed or reworded, and it is blind, by construction, to a rule
being **added**. A brief can gain "...unless the sender copied themselves"
and every pin still passes, because every pinned sentence is still present.

An audit measured the cost. Across the older verifiers, 17 of 18 and 12 of
16 brief mutations went unnoticed, including full inversions of a clash
rule and of a tie-break. The pins were not weak individually; they were
answering the wrong question. "Is this sentence still here" is not "does
this section still say only what I think it says".

So a substring pin is a good *first* line -- it names the specific
assumption and produces a readable failure -- and it needs a second line
underneath that no addition can slip past: a digest of the whole rule
section. Any edit at all breaks it.

That is deliberately coarse. Rewording a rule section without touching its
meaning will fail this, and the right response is to re-read the verifier
against the new wording and re-pin. That is the behaviour we want: a rule
the agent is graded against should not change without someone confirming
the second derivation still implements it.
"""

from __future__ import annotations

import hashlib
import re


class RuleChanged(AssertionError):
    """A pinned section of the brief is no longer what it was pinned as."""


def section(brief: str, heading: str) -> str:
    """The passage under `heading`, up to the next heading of any depth."""

    at = brief.find(heading)
    if at < 0:
        raise RuleChanged(f"the brief has no {heading!r} section")
    rest = brief[at + len(heading) :]
    end = re.search(r"^#{2,}\s", rest, re.M)
    return rest[: end.start()] if end else rest


def normalise(text: str) -> str:
    """Collapse everything that carries no meaning for a rule.

    Whitespace and emphasis change when a paragraph is rewrapped, which
    happens constantly and means nothing. Anything else -- a word, a
    number, a clause, a new sentence -- is a change to the rule.
    """

    without_emphasis = text.replace("**", "").replace("*", "").replace("`", "")
    return " ".join(without_emphasis.split()).strip().lower()


def digest(brief: str, heading: str) -> str:
    """A short, stable fingerprint of one rule section."""

    return hashlib.sha256(
        normalise(section(brief, heading)).encode("utf-8")
    ).hexdigest()[:16]


def unchanged(brief: str, heading: str, expected: str) -> None:
    """Refuse unless `heading`'s passage is exactly what was pinned.

    Catches the mutation a substring pin cannot see: an exception added to
    a rule that leaves every pinned sentence in place.
    """

    actual = digest(brief, heading)
    if actual != expected:
        raise RuleChanged(
            f"{heading!r} has changed: pinned {expected}, now {actual}.\n"
            "A substring pin would not have seen this if the edit only ADDED "
            "text. Re-read this section against the verifier that implements "
            "it, confirm the second derivation still matches, then update the "
            "pinned digest deliberately -- do not paste the new value in to "
            "make the check pass."
        )


__all__ = ["RuleChanged", "digest", "normalise", "section", "unchanged"]
