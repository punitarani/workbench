"""A standing meeting recurs on a weekday, and a weekly one on the same one.

`_recurrence_days` returned day indices under the belief that "sim days
are workdays, so 'daily' is every day index and 'weekly' is every fifth —
no calendar arithmetic, and no meeting on a Saturday that the simulation
does not have". Every clause of that was wrong about the index it
returned. A day index is a *calendar* day: `CalendarWindow.day_offset` is
`index * 86_400` from the epoch, and workdays are a filtered subset of the
range rather than a compressed one.

So `daily` put a standing meeting on every Saturday and Sunday in the
window — 27.7% of all meetings in a six-month world, which is 2/7 almost
exactly — and `weekly`, stepping five calendar days, walked a "weekly"
series through Monday, Saturday, Thursday, Tuesday, Sunday, Friday,
Wednesday and round again.

A firm whose weekly partner meeting is never twice on the same weekday is
not one anyone recognises, and the diary is what two of this dataset's
task shapes read.
"""

from datetime import date, timedelta

import pytest

from simulation.workplace.compile import _recurrence_days

MONDAY = date(2026, 1, 5)
WINDOW = 180


def _weekdays(indices, epoch=MONDAY):
    return {(epoch + timedelta(days=i)).weekday() for i in indices}


def test_daily_never_lands_on_a_weekend() -> None:
    days = _recurrence_days("daily", WINDOW, MONDAY)
    assert days
    assert max(_weekdays(days)) < 5, "a standing meeting was scheduled on a weekend"


def test_daily_covers_every_workday() -> None:
    """The filter must not also thin the series — a daily meeting happens
    daily."""

    days = _recurrence_days("daily", WINDOW, MONDAY)
    expected = [i for i in range(WINDOW) if (MONDAY + timedelta(days=i)).weekday() < 5]
    assert list(days) == expected


def test_weekly_is_always_the_same_weekday() -> None:
    days = _recurrence_days("weekly", WINDOW, MONDAY)
    assert len(_weekdays(days)) == 1, (
        f"a weekly series rotated through {sorted(_weekdays(days))}"
    )


def test_weekly_is_seven_days_apart() -> None:
    days = _recurrence_days("weekly", WINDOW, MONDAY)
    assert all(b - a == 7 for a, b in zip(days, days[1:], strict=False))


def test_weekly_recurs_about_once_a_week() -> None:
    """Guarding the other direction: a fix that returned one instance
    would satisfy every assertion above."""

    days = _recurrence_days("weekly", WINDOW, MONDAY)
    assert len(days) == pytest.approx(WINDOW / 7, abs=1)


@pytest.mark.parametrize("weekday", range(7))
def test_an_epoch_on_any_day_still_starts_on_a_workday(weekday: int) -> None:
    """A window that opens on a Saturday must not put its first standing
    meeting there."""

    epoch = MONDAY + timedelta(days=weekday)
    for recurrence in ("daily", "weekly", "once"):
        days = _recurrence_days(recurrence, WINDOW, epoch)
        first = (epoch + timedelta(days=days[0])).weekday()
        assert first < 5, f"{recurrence} opened on weekday {first}"


def test_a_one_off_is_one_meeting() -> None:
    assert len(_recurrence_days("once", WINDOW, MONDAY)) == 1
