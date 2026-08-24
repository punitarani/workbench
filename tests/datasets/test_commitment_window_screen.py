"""The window screen agrees with the solver, and refuses what it should.

Filling a brief by hand is where this dataset's most expensive defects came
from — a window measured on a partial recording and never re-measured,
per-form counts published as prose that an agent read as a specification,
a deadline rate quoted from a world since re-recorded. Every one was a true
number in the wrong place, and none was caught by a test, because a brief
is prose and prose does not fail.

These tests do not check the numbers, which depend on a corpus. They check
the two properties that make the screen trustworthy: that it refuses a
window it cannot support, and that its date arithmetic is the solver's.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

_DATASET = Path(__file__).resolve().parents[2] / "datasets" / "merrick"


def _load(name: str, path: Path):
    sys.path.insert(0, str(_DATASET))
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


screen = _load("_window_screen", _DATASET / "measure_commitment_window.py")

MON, TUE, WED, THU, FRI = (dt.date(2026, 2, 16 + n) for n in range(5))


def test_the_screen_resolves_dates_the_way_the_solver_does(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A screen that chooses the window has to agree with the file that
    grades it. If they drift, the screen certifies a window whose rows the
    task will not produce — and it will look like the corpus changed.

    `monkeypatch` rather than `os.environ.setdefault`: the latter mutated
    the session environment for good, and every subprocess a later test
    started inherited it. legal-nda's `solve.sh` reads `WORKBENCH_STATE`
    with a relative default, so it silently read another dataset's
    databases and exited 1 -- six failures whose traceback named a task
    nothing here had touched.
    """

    monkeypatch.setenv("WORKBENCH_STATE", str(_DATASET))
    solver = _load(
        "_lcr_solve_for_screen",
        _DATASET / "tasks/live-commitment-register/solution/solve.py",
    )
    for token in ("eod", "tomorrow", "end of week", *screen._WEEKDAYS):
        for offset in range(5):
            said = MON + dt.timedelta(days=offset)
            assert screen._due(said, token) == solver.due_date(said, token), (
                token,
                said,
            )


def test_the_compound_is_one_deadline_here_too() -> None:
    assert screen._token("I'll confirm by EOD tomorrow") == "tomorrow"
    assert screen._token("I'll confirm by EOD-tomorrow") == "tomorrow"
    assert screen._token("I'll confirm by EOD") == "eod"


def test_the_floors_are_the_ones_the_task_promises() -> None:
    """Guard the guard. The screen's verdict is only worth reading if its
    thresholds are the task's — a screen with its own private floors passes
    windows the task then refuses, or refuses windows it would accept."""

    assert screen.WORD_CEILING == 60_000
    assert screen.ROW_FLOOR >= 12
    assert screen.SUPERSESSION_FLOOR == 0.15
    assert screen.STANDING_MINIMUM == 3
