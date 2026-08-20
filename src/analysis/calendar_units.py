"""Calendar starts that are not seconds-from-epoch.

A simulated world keeps time as seconds from the run's epoch. Three
incompatible units turned up in one recorded calendar, all written by the
same field:

* **seconds from epoch** — correct, 716 of 782 events;
* **seconds from midnight** — 45 events, where an author wrote a wall-clock
  time (`31500` = 08:45) into an offset field. Every one of them lands on
  day zero;
* **absolute Unix timestamps** — 21 events, which land fifty-four years
  past the epoch.

Neither wrong unit raises. Both produce a plausible integer, project into a
plausible row, and serve a plausible event, so nothing in the pipeline
objects. What they produce is a diary that says the firm held forty-five
meetings before it opened and twenty-one in 2081.

**The damage is not proportional to the count.** Those 45 events are 5.8%
of the calendar and caused **96% of all scheduling conflicts** in the
world, because collapsing onto one day makes every one of them overlap
every other. A task was designed on that signal, measured a healthy-looking
4.4:1 ratio of near-miss decoys to real conflicts, and was retired only
after the conflicts were grouped by date. A rate says nothing about whether
the thing it counts is real.

This is a detector, not a repair. Which day a wall-clock time was meant for
is not recoverable, so the honest move is to refuse to ship the world
quietly rather than to invent the missing information.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

# A start below one day is a time-of-day that lost its date. This is safe
# because a legitimate event on the epoch's own first day still carries the
# epoch offset for that day, which is at minimum the working day's start.
TIME_OF_DAY = 86_400

# Unix timestamps for any plausible present are far above any offset a
# simulated run of months could reach; a decade of simulated seconds is
# ~3.2e8, and 1e9 is comfortably clear of it.
ABSOLUTE_EPOCH = 1_000_000_000


@dataclass(frozen=True, slots=True)
class Suspect:
    event_id: str
    start: int
    unit: str


@dataclass(frozen=True, slots=True)
class Report:
    total: int
    suspects: tuple[Suspect, ...]

    @property
    def share(self) -> float:
        return len(self.suspects) / self.total if self.total else 0.0

    @property
    def ok(self) -> bool:
        return not self.suspects

    def by_unit(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for suspect in self.suspects:
            counts[suspect.unit] = counts.get(suspect.unit, 0) + 1
        return counts

    def summary(self) -> str:
        if self.ok:
            return f"{self.total} calendar starts, all seconds-from-epoch"
        parts = ", ".join(f"{n} {unit}" for unit, n in sorted(self.by_unit().items()))
        return (
            f"{len(self.suspects)} of {self.total} calendar starts "
            f"({self.share:.1%}) are not seconds-from-epoch: {parts}"
        )


def classify(start: int) -> str | None:
    """The unit a start was probably written in, or None when it is right."""

    if start < 0:
        return "negative"
    if start < TIME_OF_DAY:
        return "seconds-from-midnight"
    if start >= ABSOLUTE_EPOCH:
        return "absolute-unix"
    return None


def inspect(events: Iterable[tuple[str, int]]) -> Report:
    """Classify every `(event_id, start)` pair."""

    rows = list(events)
    return Report(
        total=len(rows),
        suspects=tuple(
            Suspect(event_id, start, unit)
            for event_id, start in rows
            if (unit := classify(start)) is not None
        ),
    )


__all__ = [
    "ABSOLUTE_EPOCH",
    "TIME_OF_DAY",
    "Report",
    "Suspect",
    "classify",
    "inspect",
]
