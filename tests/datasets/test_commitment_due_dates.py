"""The date arithmetic of the live commitment register.

This is the part of the task that is a property of the English rather than
of the recording, so it is written and settled before the corpus lands.
Every convention asserted here is one the corpus exercises, with the count
that earned it its place in the brief.

The register grades the resolved date rather than the word, and that is the
whole mechanism: `EOD` said in two different meetings is the same word and
two different obligations. Measured across five windows, grading the token
hands a reader who guesses the commonest word 47-69% of the field for free;
grading the date hands them 16-23%, and roughly doubles the error rate of a
reader who takes each person's first statement (to 62-72%).
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_TASK = (
    Path(__file__).resolve().parents[2]
    / "datasets/merrick/tasks/live-commitment-register"
)


def _solver():
    """Import the solver without a corpus.

    It reads `WORKBENCH_STATE` at import, and the window calls `measure()`,
    which raises. Both are deliberate — the file must fail loudly when run
    unmeasured — so the date logic was put above that line precisely so it
    could be imported and tested on its own.
    """

    import os

    os.environ.setdefault("WORKBENCH_STATE", str(_TASK))
    sys.path.insert(0, str(_TASK.parents[1]))
    spec = importlib.util.spec_from_file_location(
        "_lcr_solve", _TASK / "solution/solve.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


solve = _solver()

MON, TUE, WED, THU, FRI = (dt.date(2026, 2, 16 + n) for n in range(5))


# ------------------------------------------------------------------ tokens


def test_eod_tomorrow_is_one_deadline_and_it_means_tomorrow() -> None:
    """The commonest two-form phrase in the corpus: 47 of 178 turns.

    A form table that tries `EOD` before the compound resolves a quarter of
    everything the task grades to the wrong day — and does it silently,
    because `eod` is a perfectly valid token that produces a perfectly
    plausible date.
    """

    assert solve.deadline_token("I'll confirm the date by EOD tomorrow") == "tomorrow"
    assert solve.deadline_token("I'll have it COB tomorrow") == "tomorrow"
    assert solve.deadline_token("I'll have it by end of day tomorrow") == "tomorrow"


def test_a_bare_eod_is_still_today() -> None:
    assert solve.deadline_token("I'll have it by EOD") == "eod"
    assert solve.deadline_token("I'll get it out by close of business") == "eod"


def test_one_turn_names_one_deadline() -> None:
    """40% of commitment turns name two forms.

    Collecting both would make a single sentence disagree with itself, and
    supersession is computed by comparing a speaker's first statement to
    their last — so a fake disagreement inside one turn becomes a fake
    revision.
    """

    assert solve.deadline_token("I'll have it Thursday, Friday at the latest") in {
        "thursday",
        "friday",
    }
    assert solve.deadline_token("I'll start tomorrow and finish by Thursday") in {
        "tomorrow",
        "thursday",
    }


def test_a_turn_with_no_deadline_names_none() -> None:
    assert solve.deadline_token("I'll pick this up and come back to you") is None
    assert solve.deadline_token("") is None


# ------------------------------------------------------------------- dates


def test_eod_is_the_day_it_was_said() -> None:
    assert solve.due_date(WED, "eod") == WED


def test_tomorrow_skips_the_weekend() -> None:
    """Said on a Friday, `tomorrow` means Monday — 3 turns in 56 days.

    The firm records no weekend days at all: 58 recorded days, every one
    Monday to Friday. A Saturday deadline would be a date on which nobody
    could deliver, so it is not one the register can report.
    """

    assert solve.due_date(THU, "tomorrow") == FRI
    assert solve.due_date(FRI, "tomorrow") == MON + dt.timedelta(days=7)


def test_end_of_week_is_that_weeks_friday() -> None:
    assert solve.due_date(MON, "end of week") == FRI
    assert solve.due_date(THU, "end of week") == FRI


def test_end_of_week_said_on_friday_is_that_same_friday() -> None:
    """Not a week later. Somebody saying "end of week" on Friday morning
    means today, and reading it as next Friday moves a live commitment a
    week into the future — the exact error the register exists to catch."""

    assert solve.due_date(FRI, "end of week") == FRI


def test_a_weekday_names_its_next_occurrence() -> None:
    assert solve.due_date(MON, "thursday") == THU
    assert solve.due_date(TUE, "friday") == FRI


def test_a_weekday_earlier_in_the_week_is_next_week() -> None:
    """26 turns in 56 days name a weekday already past.

    Said on Thursday, "Tuesday" cannot mean two days ago — a deadline in the
    past is not a deadline. It is next Tuesday.
    """

    assert solve.due_date(THU, "tuesday") == TUE + dt.timedelta(days=7)
    assert solve.due_date(FRI, "monday") == MON + dt.timedelta(days=7)


def test_a_weekday_said_on_that_same_weekday_is_next_week() -> None:
    """3 turns. Somebody saying "Thursday" in Thursday's docket call is
    talking about the next one, not the meeting they are sitting in."""

    assert solve.due_date(THU, "thursday") == THU + dt.timedelta(days=7)


@pytest.mark.parametrize("token", ["eod", "tomorrow", "end of week", *solve.WEEKDAYS])
def test_every_token_resolves_to_a_working_day(token: str) -> None:
    """Guard the guard.

    Each convention above is asserted on one or two dates. This asserts the
    property they all have to share, across every starting weekday: a
    register of what the firm owes cannot name a day the firm does not work.
    """

    for offset in range(5):
        said = MON + dt.timedelta(days=offset)
        assert solve.due_date(said, token).weekday() < 5, (token, said)


def test_the_resolved_date_is_never_before_the_day_it_was_said() -> None:
    for offset in range(5):
        said = MON + dt.timedelta(days=offset)
        for token in ("eod", "tomorrow", "end of week", *solve.WEEKDAYS):
            assert solve.due_date(said, token) >= said, (token, said)
