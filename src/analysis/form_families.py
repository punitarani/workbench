"""Choose a literalism task's word family by measuring, not by intuition.

A register built on "every message that says X" is the hardest shape this
tree has measured — and which X you pick decides whether it lands in band
or at ceiling. The author's ear is not evidence. This is the query that
is.

Three numbers per candidate, and only the third predicts:

**Liveness.** Both spellings must actually occur. Two families that read
perfectly on paper were dead on the corpus — one second spelling appeared
in a single message out of 1,585, another in none at all. A rule whose
second form never fires is a one-form rule with extra words.

**Exclusive minority share.** Whether the second spelling *earns its
place*. The obvious version of this — each form's share of all form hits
— answers the wrong question, because a message carrying both forms is
counted under both. A family where the rarer form appears ten times and
every one of those messages also carries the commoner form scores 0.33
and passes a 0.20 floor, while contributing **no row the first form would
not already have matched**. What matters is how many messages each form
matches *alone*.

**Off-sense share — the one that matters.** How often the admitted word
appears meaning something *other* than the thing the register is named
after. This corrects the intuition the whole shape invites: that the
lever is dense *excluded* inflections, the `completion`/`completes` a
careless matcher would over-admit. It is not. A word-boundary match is
never confused by a neighbouring inflection — only a reader working from
meaning is, and it is the reader the task is measuring.

In the family behind the hardest measured task, a majority of occurrences
of the admitted word are adjectival (*the complete picture*, *the
complete, dated calendar*), idiomatic, future (*I can typically complete
this analysis*) or conditional (*once that call is complete*) — 79%
inside the graded window. Those are precisely the rows the weaker tiers
dropped: a model reading for sense filters them out, and the rule says
they count.

Off-sense cannot be counted mechanically — that is the point of it. This
module measures what it can and hands back a seeded sample of occurrences
in context for a human to classify.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Word boundary defined on *letters*, not `\b`. The difference is real and
# is about digits and underscores: `\b` treats `complete2` and
# `complete_x` as word-boundary matches, and a corpus with reference
# numbers or identifiers in it will produce rows an instruction cannot
# justify. Letters-only is also the rule a professional brief can state in
# one sentence — "no letter immediately before it and no letter
# immediately after" — which is the version the agent is graded against.
def _whole_word(word: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])", re.IGNORECASE)


@dataclass(frozen=True)
class Family:
    """Two admitted spellings, and the inflections the rule excludes."""

    name: str
    forms: tuple[str, ...]
    excluded: tuple[str, ...] = ()


@dataclass(frozen=True)
class FamilyReport:
    name: str
    messages: int
    per_form: tuple[tuple[str, int], ...]
    # Messages matched by exactly one form. This, not `per_form`, is what
    # says whether a spelling grades anything of its own.
    exclusive_per_form: tuple[tuple[str, int], ...]
    occurrences: int
    exclusion_only_messages: int
    samples: tuple[str, ...] = ()

    @property
    def alive(self) -> bool:
        """Every admitted form matches at least one message on its own.

        Not merely "appears somewhere": a form that only ever occurs
        alongside the other one is decorative, and a rule naming it is a
        one-form rule with extra words.
        """

        return all(count > 0 for _, count in self.exclusive_per_form)

    @property
    def minority_share(self) -> float:
        """The rarer form's share of matched messages, counting only the
        messages it matches *alone*. 0.0 when nothing matches."""

        counts = [count for _, count in self.exclusive_per_form]
        return (min(counts) / self.messages) if self.messages else 0.0


def measure_family(
    bodies: list[str],
    family: Family,
    *,
    sample: int = 30,
    context: int = 70,
    seed: int = 11,
) -> FamilyReport:
    """Count a family over a corpus and sample its occurrences in context."""

    patterns = {form: _whole_word(form) for form in family.forms}
    excluded = [_whole_word(word) for word in family.excluded]

    per_form: dict[str, int] = {form: 0 for form in family.forms}
    exclusive: dict[str, int] = {form: 0 for form in family.forms}
    matched = 0
    exclusion_only = 0
    windows: list[str] = []

    for body in bodies:
        if not body:
            continue
        here: list[str] = []
        for form, pattern in patterns.items():
            found = list(pattern.finditer(body))
            if found:
                here.append(form)
                per_form[form] += 1
                for match in found:
                    start = max(0, match.start() - context)
                    end = min(len(body), match.end() + context)
                    windows.append(" ".join(body[start:end].split()))
        if here:
            matched += 1
            if len(here) == 1:
                exclusive[here[0]] += 1
        elif any(pattern.search(body) for pattern in excluded):
            exclusion_only += 1

    # Seeded, so the sample a decision was made on can be reproduced.
    import random

    picked = tuple(random.Random(seed).sample(windows, min(sample, len(windows))))
    return FamilyReport(
        name=family.name,
        messages=matched,
        per_form=tuple(sorted(per_form.items())),
        exclusive_per_form=tuple(sorted(exclusive.items())),
        occurrences=len(windows),
        exclusion_only_messages=exclusion_only,
        samples=picked,
    )


# Set against the family that produced the hardest measured task: 25 rows
# **in its graded window**, and 79% off-sense there. The row floor is
# hygiene, not the lever — off-sense is where the margin lives.
#
# The units matter and were wrong once. `measure_family` counts whatever
# bodies it is handed, and handing it the whole corpus produced 110 for
# the calibration family against a floor derived from its 25-row window —
# a fourfold mismatch that would pass a family with a quarter of the rows
# it needs. **Screen the window a task will actually grade**, not the
# corpus it sits in; `screen()` refuses to guess which it was given.
MIN_ROWS = 20
MIN_MINORITY_SHARE = 0.20
MIN_OFF_SENSE_SHARE = 0.60


def screen(
    report: FamilyReport,
    *,
    off_sense_share: float | None = None,
    windowed: bool = False,
) -> tuple[str, ...]:
    """Why this family is not the one, as readable sentences.

    ``off_sense_share`` is supplied by whoever classified the sample. It is
    deliberately not defaulted: a family that has not been read cannot pass,
    and silently treating "unmeasured" as "fine" is how the decoy metric
    won in the first place.

    ``windowed`` asserts the report was built from the bodies a task will
    actually grade rather than the whole corpus. The floors are calibrated
    in window rows, and comparing them to a corpus count passes a family
    with a fraction of the rows it needs.
    """

    problems: list[str] = []
    if off_sense_share is not None and not 0.0 <= off_sense_share <= 1.0:
        # A share outside [0,1] is a units error — somebody passed 79
        # meaning 79%. Silently comparing it to 0.60 passes everything.
        raise ValueError(
            f"off_sense_share must be a fraction in [0,1], got {off_sense_share!r}"
        )
    if off_sense_share is not None and off_sense_share != off_sense_share:
        raise ValueError("off_sense_share is NaN; every comparison against it is False")
    if not windowed:
        problems.append(
            "measured over an unwindowed corpus — the row floor is "
            "calibrated in the rows a task grades, and a corpus count "
            "clears it with a fraction of them"
        )
    if not report.alive:
        dead = [form for form, count in report.exclusive_per_form if count == 0]
        problems.append(
            f"{', '.join(dead)} never matches a message on its own — a form "
            "that only ever appears beside the other one adds no row, so "
            "the rule naming it is a one-form rule with extra words"
        )
    if report.messages < MIN_ROWS:
        problems.append(
            f"only {report.messages} messages carry a form, under the "
            f"{MIN_ROWS}-row floor for partial credit"
        )
    if report.minority_share < MIN_MINORITY_SHARE:
        problems.append(
            f"minority form is {report.minority_share:.1%} of hits, under "
            f"{MIN_MINORITY_SHARE:.0%} — the task would grade one spelling"
        )
    if off_sense_share is None:
        problems.append(
            "off-sense share not measured — classify the sample by hand; "
            "this is the number that predicts the miss"
        )
    elif off_sense_share < MIN_OFF_SENSE_SHARE:
        problems.append(
            f"off-sense share is {off_sense_share:.0%}, under "
            f"{MIN_OFF_SENSE_SHARE:.0%} — too few occurrences mean anything "
            "other than the register's own idea, so a model reading for "
            "sense agrees with the rule and the task sits at ceiling"
        )
    return tuple(problems)


__all__ = [
    "MIN_MINORITY_SHARE",
    "MIN_OFF_SENSE_SHARE",
    "MIN_ROWS",
    "Family",
    "FamilyReport",
    "measure_family",
    "screen",
]
