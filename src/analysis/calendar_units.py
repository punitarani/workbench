"""Calendar starts that are not seconds-from-epoch.

A simulated world keeps time as seconds from the run's epoch. Three
incompatible units turned up in one recorded calendar, all written by the
same field:

* **a wall-clock time that lost its date** — 40 events, written as
  `31500` (08:45) into a field holding an offset, so each lands on the
  epoch's own day;
* **an absolute Unix timestamp** — 23 events, landing fifty-four years
  past the epoch.

Judging these by magnitude does not work: with a midnight epoch, `31500` is
also exactly what a legitimate 08:45 meeting on the first day looks like,
and 8 such events in this world are real. The discriminator is causal —
a start earlier than the moment the event was recorded was scheduled into
the past.

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

from core.simtime import misread_unit

# The rule itself lives in `core.simtime`: the projection that drops
# corrupt rows and this gate that reports them have to agree, and two copies
# of a boundary drift the first time one is tuned.


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


def classify(start: int, recorded_at: int) -> str | None:
    """Why a start cannot be simulated time, or None when it is fine."""

    return misread_unit(start, recorded_at)


def inspect(events: Iterable[tuple[str, int, int]]) -> Report:
    """Classify every `(event_id, start, recorded_at)` triple.

    `recorded_at` is required rather than optional: it is the whole reason
    this is a measurement and not a restatement of the threshold. An earlier
    version took only the start, judged it by magnitude, and could not tell
    a first-day morning meeting from a wall-clock time that had lost its
    date -- and the "verification" of that version filtered the world by the
    same threshold that defined the fault.
    """

    rows = list(events)
    return Report(
        total=len(rows),
        suspects=tuple(
            Suspect(event_id, start, unit)
            for event_id, start, recorded_at in rows
            if (unit := classify(start, recorded_at)) is not None
        ),
    )


__all__ = [
    "Report",
    "Suspect",
    "classify",
    "inspect",
]
