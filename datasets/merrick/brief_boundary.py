"""The window boundary, read back off the brief and cross-checked.

A window that is off by one day makes every row wrong together while every
row-level comparison stays green: both derivations hold the boundary as a
number, the number agrees with itself, and nothing reads the sentence the
agent was actually given. An audit of this repo's verifiers found exactly
that -- two of them took the window from `argv` and never looked at
`window_end` at all.

So the boundary is asserted three ways, and they have to agree:

1. the verifier **transcribes** it, as its own `measure()` value, which
   raises while a task is staged and keeps the placeholder visible to the
   build gate;
2. the **brief** must state that same date, with the weekday it really
   falls on -- catching a boundary copied wrongly into the prose the agent
   reads;
3. the **oracle** must report that same `window_end` -- catching a solver
   windowing on something else.

Shared between verifiers on purpose. The independence rule is about a
verifier not reusing its *solver's* expression of the rule; boundary
parsing is neither file's rule, and three hand-copies of it would drift.
"""

from __future__ import annotations

import calendar
import datetime
import re

_MONTHS = {name.lower(): n for n, name in enumerate(calendar.month_name) if name}
_WEEKDAYS = {name.lower(): n for n, name in enumerate(calendar.day_name)}


class BoundaryDisagreement(AssertionError):
    """The brief, the verifier and the oracle do not name the same day."""


def _dates_in(text: str) -> set[datetime.date]:
    """Every date the passage names, in either spelling."""

    found: set[datetime.date] = set()
    for iso in re.findall(r"\b(\d{4})-(\d{2})-(\d{2})\b", text):
        try:
            found.add(datetime.date(int(iso[0]), int(iso[1]), int(iso[2])))
        except ValueError:
            continue
    for day, month, year in re.findall(r"\b(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\b", text):
        number = _MONTHS.get(month.lower())
        if number:
            try:
                found.add(datetime.date(int(year), number, int(day)))
            except ValueError:
                continue
    return found


def stated_boundary(brief: str, transcribed: datetime.date, section: str) -> None:
    """Refuse unless the brief names `transcribed`, with the right weekday.

    `section` is the heading whose passage holds the boundary, so a date
    mentioned in a worked example elsewhere cannot satisfy this.
    """

    at = brief.find(section)
    if at < 0:
        raise BoundaryDisagreement(f"the brief has no {section!r} section")
    rest = brief[at + len(section) :]
    nxt = rest.find("\n## ")
    passage = rest if nxt < 0 else rest[:nxt]

    named = _dates_in(passage)
    if transcribed not in named:
        raise BoundaryDisagreement(
            f"the verifier windows on {transcribed.isoformat()} and the "
            f"brief's {section!r} names {sorted(d.isoformat() for d in named)}. "
            "One of them was copied wrongly, and a window off by a day makes "
            "every row wrong together while every row comparison stays green."
        )

    # A brief that names a weekday the date does not fall on is a brief the
    # reader will follow to a different day than the oracle used.
    spoken = {w for w in _WEEKDAYS if re.search(rf"\b{w}\b", passage, re.I)}
    if spoken:
        correct = calendar.day_name[transcribed.weekday()].lower()
        if correct not in spoken:
            raise BoundaryDisagreement(
                f"the brief calls the boundary {sorted(spoken)} but "
                f"{transcribed.isoformat()} is a {correct}"
            )


def stated_working_days(
    brief: str, epoch: datetime.date, last_day: datetime.date, section: str
) -> None:
    """If the window section quotes a working-day count, make it true.

    Every brief restates its window twice: once as the boundary date, which
    is operative, and once as "the firm's N working days", which is the way a
    reader actually thinks about a span. The second is a free number — it can
    say anything and nothing notices, because only the date is windowed on.

    It is worth checking anyway. The two are meant to be transcribed as a
    matched pair from one printed line, so a disagreement means one of them
    was typed rather than copied, and the one that was typed might have been
    the date.

    Silent when the passage quotes no count: not every brief carries one, and
    a check that invents a requirement is worse than no check.
    """

    at = brief.find(section)
    if at < 0:
        raise BoundaryDisagreement(f"the brief has no {section!r} section")
    rest = brief[at + len(section) :]
    nxt = rest.find("\n## ")
    passage = (rest if nxt < 0 else rest[:nxt]).replace("*", "")

    found = re.search(r"\b(\d{1,3})\s+working days\b", passage)
    if not found:
        return
    claimed = int(found.group(1))
    actual = sum(
        1
        for offset in range((last_day - epoch).days + 1)
        if (epoch + datetime.timedelta(days=offset)).weekday() < 5
    )
    if claimed != actual:
        raise BoundaryDisagreement(
            f"the brief says {claimed} working days and {epoch.isoformat()} "
            f"through {last_day.isoformat()} is {actual}. The date and the "
            "count are meant to come from one measured line as a pair; if "
            "they disagree, one was typed rather than copied — and it may "
            "have been the date."
        )


def window_days(epoch: datetime.date, last_day: datetime.date) -> int:
    """Calendar days from the epoch through `last_day`, inclusive.

    Calendar, not working, days: the solvers cut on `days * 86_400`, and
    the two counts differ by every weekend in the window. The briefs quote
    a working-day figure because that is what a reader thinks in, which is
    why the boundary *date* is the thing carried across files rather than
    either count.
    """

    span = (last_day - epoch).days + 1
    if span <= 0:
        raise BoundaryDisagreement(
            f"boundary {last_day} is not after the epoch {epoch}"
        )
    return span


def check_reported(oracle: dict, transcribed: datetime.date) -> None:
    """The oracle's own `window_end` must be the boundary too."""

    reported = oracle.get("window_end")
    if str(reported) != transcribed.isoformat():
        raise BoundaryDisagreement(
            f"the oracle reports window_end={reported!r} and the boundary is "
            f"{transcribed.isoformat()}"
        )


__all__ = [
    "BoundaryDisagreement",
    "stated_working_days",
    "check_reported",
    "stated_boundary",
    "window_days",
]
