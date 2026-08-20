"""Generic premise checks: liveness, concentration, degeneracy, admission.

These operate on plain lists of dicts and callables, so they work against
any world regardless of its schema. Each returns a small report rather
than printing, so callers can assert on them in a gate.

**Nothing measured is not the same as nothing wrong.** Every report's `ok`
is False when it had no rows to look at, because a helper that returns
"clean" for an empty list is exactly the check-that-cannot-fail this method
warns about — and an empty list is the most common way a premise check goes
wrong, since a mistyped field name yields one silently. `empty` says which
of the two happened.

The one thing they cannot do for you is read the matched rows. A count
agreeing with your premise is not evidence for it -- see the skill.
"""

from __future__ import annotations

import collections
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Liveness:
    counts: dict[str, int]
    dead: tuple[str, ...]
    dominant: tuple[str, float] | None

    @property
    def empty(self) -> bool:
        return not any(self.counts.values())

    @property
    def ok(self) -> bool:
        return not self.dead and not self.empty


def liveness(
    items: Iterable[Any],
    patterns: dict[str, Callable[[Any], bool]],
) -> Liveness:
    """How often each admitted form actually occurs.

    A rule listing seven forms where the world writes four scores three
    sevenths of its own vocabulary against nothing, and the misses read as
    model failure. `dominant` names any single form carrying most of the
    mass, which is the other half of the same problem: a rule that is
    effectively one form wearing seven hats.
    """

    rows = list(items)
    counts = {name: sum(1 for r in rows if test(r)) for name, test in patterns.items()}
    total = sum(counts.values())
    top = max(counts.items(), key=lambda kv: kv[1], default=None)
    return Liveness(
        counts=counts,
        dead=tuple(sorted(n for n, c in counts.items() if c == 0)),
        dominant=(top[0], top[1] / total)
        if top and total and top[1] / total > 0.6
        else None,
    )


@dataclass(frozen=True, slots=True)
class Concentration:
    per_bucket: dict[Any, int]
    total: int
    worst: tuple[Any, float] | None
    buckets_with_any: int

    @property
    def empty(self) -> bool:
        return self.total == 0

    @property
    def ok(self) -> bool:
        return self.worst is None and not self.empty


def concentration(
    items: Iterable[Any],
    key: Callable[[Any], Any],
    threshold: float = 0.5,
) -> Concentration:
    """Is the signal spread, or is it one bucket wearing a rate?

    A rate over a window can be dominated by what happens at one edge of
    it, and the total never shows it. Measured on a real world: 54
    conflicts looked like a healthy 4.4:1 trap ratio, and 47 of them fell
    on the first day, where the world seeds far more events than it later
    creates. Outside that burst the world produced one.

    `threshold` is the share of all signal in a single bucket that counts
    as an artifact. Half is deliberately generous -- real concentration in
    these worlds has run to 87%.
    """

    rows = list(items)
    per = collections.Counter(key(r) for r in rows)
    total = len(rows)
    worst = None
    if total:
        bucket, count = per.most_common(1)[0]
        if count / total > threshold:
            worst = (bucket, count / total)
    return Concentration(
        per_bucket=dict(per), total=total, worst=worst, buckets_with_any=len(per)
    )


@dataclass(frozen=True, slots=True)
class Degeneracy:
    shares: dict[str, float]
    constant: tuple[str, ...]
    near_constant: tuple[str, ...] = field(default=())

    @property
    def empty(self) -> bool:
        return not self.shares

    @property
    def ok(self) -> bool:
        return not self.constant and not self.near_constant and not self.empty


def degeneracy(
    rows: Sequence[dict],
    fields: Iterable[str],
    near: float = 0.95,
) -> Degeneracy:
    """Does every graded field discriminate, or is one a free point?

    A constant column grades nothing while looking like work. One
    cross-surface boolean measured true for 98 of 98 rows, because
    everyone who touches a document logs time the same day.
    """

    shares: dict[str, float] = {}
    constant: list[str] = []
    nearly: list[str] = []
    for name in fields:
        seen = collections.Counter(
            # Lists are unhashable and appear as graded fields; compare by
            # their rendered form rather than dropping the column silently.
            tuple(v) if isinstance(v, list) else v
            for v in (r.get(name) for r in rows)
        )
        if not seen:
            continue
        share = seen.most_common(1)[0][1] / sum(seen.values())
        shares[name] = share
        if len(seen) == 1:
            constant.append(name)
        elif share >= near:
            nearly.append(name)
    return Degeneracy(
        shares=shares, constant=tuple(constant), near_constant=tuple(nearly)
    )


@dataclass(frozen=True, slots=True)
class Admission:
    admitted: int
    candidates: int
    rate: float
    band: str
    advice: str


def admission(admitted: int, candidates: int) -> Admission:
    """Is the rule worth applying, or does reporting everything win?

    Above ~80%, "report everything" scores near 0.9 without reading. Below
    ~2% the task is a needle hunt, which is bimodal and lands at 0 or 1
    rather than in a band. The repair for a too-generous rule is usually
    to invert it onto the minority class, where over-admission destroys
    precision and skimming destroys recall.
    """

    rate = admitted / candidates if candidates else 0.0
    if rate >= 0.8:
        band, advice = "too generous", "invert the rule onto the minority class"
    elif rate < 0.02:
        band, advice = "needle hunt", "bound the search, or retire the premise"
    elif 0.15 <= rate <= 0.4:
        band, advice = "good", "both precision and recall bite here"
    else:
        band, advice = "workable", "check the trap-to-signal ratio before committing"
    return Admission(admitted, candidates, rate, band, advice)


__all__ = [
    "Admission",
    "Concentration",
    "Degeneracy",
    "Liveness",
    "admission",
    "concentration",
    "degeneracy",
    "liveness",
]
