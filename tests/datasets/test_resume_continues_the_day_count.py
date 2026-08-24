"""A resumed recording must not restart its telemetry day counter.

`_DayTracker` started at `day_index = -1` unconditionally, so a run stopped
at day 13 and resumed wrote its next day as index 0. The `day` date field
stayed correct, so the rows look fine one at a time and only the *sequence*
is broken — which is the half every band, rate and trend is computed over.

Observed live: v7 paused at 14 recorded days and resumed, and its next
telemetry row read `day_index 0` while the store showed the simulation
correctly continuing to calendar day 21 with no duplicated dates.
"""

from __future__ import annotations

import json
from pathlib import Path

from dataset_modules import dataset_module

epoch = dataset_module("merrick", "run_epoch")


def _write(path: Path, days: list[str]) -> None:
    path.write_text(
        "\n".join(
            json.dumps({"kind": "day", "day": d, "day_index": i})
            for i, d in enumerate(days)
        )
        + "\n"
    )


def test_a_fresh_run_starts_at_zero(tmp_path: Path) -> None:
    assert epoch._days_recorded(tmp_path / "telemetry.jsonl") == 0


def test_a_resume_continues_from_what_was_written(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    _write(path, ["2026-01-05", "2026-01-06", "2026-01-07"])
    assert epoch._days_recorded(path) == 3

    tracker = epoch._DayTracker.__new__(epoch._DayTracker)
    epoch._DayTracker.__init__(
        tracker, writer=None, budget=None, days_already_recorded=3
    )
    assert tracker._day_index == 2, "the next day started must become index 3"


def test_distinct_dates_not_rows(tmp_path: Path) -> None:
    """A day counted twice must not advance the index twice.

    Rows are counted by date rather than by line because a run killed
    between `sim.day.started` and `sim.day.ended` writes no row at all —
    a row count would be right by accident, a date count is right on
    purpose — and because a duplicated row must not shift every later day.
    """

    path = tmp_path / "telemetry.jsonl"
    _write(path, ["2026-01-05", "2026-01-06", "2026-01-06"])
    assert epoch._days_recorded(path) == 2


def test_a_truncated_line_does_not_refuse_the_resume(tmp_path: Path) -> None:
    """Telemetry is not the recording. Refusing to resume a twenty-hour run
    over a half-written JSON line would be the cure being worse."""

    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        json.dumps({"kind": "day", "day": "2026-01-05"}) + '\n{"kind": "da\n'
    )
    assert epoch._days_recorded(path) == 1


def test_non_day_rows_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "telemetry.jsonl"
    path.write_text(
        json.dumps({"kind": "segment", "day": "2026-01-05"})
        + "\n"
        + json.dumps({"kind": "day", "day": "2026-01-05"})
        + "\n"
    )
    assert epoch._days_recorded(path) == 1
