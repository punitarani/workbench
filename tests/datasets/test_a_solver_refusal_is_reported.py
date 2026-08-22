"""A staged solver must fail with its own sentence, not a traceback.

`build_tasks`'s staged check knows two shapes of placeholder: `«MEASURE` in
the brief, and a `measure("` call in Python. A task can use a third — a
module constant left as `None` that `main()` refuses on — and such a task
passes the check, gets built, and used to die as a `CalledProcessError`
naming a subprocess and an exit code, twenty lines from the one sentence
saying which value is missing.

The check cannot be widened to catch the third shape: the `«MEASURE` text
inside a solver is guidance for whoever fills it and survives filling, so
flagging it would report every finished task as staged. Carrying the
solver's own refusal up is both simpler and exact.
"""

from __future__ import annotations

import subprocess

import pytest
from dataset_modules import dataset_module

build = dataset_module("merrick", "build_tasks")


def _outcome(code: int, stderr: str = "", stdout: str = ""):
    return subprocess.CompletedProcess(
        args=["solve.py"], returncode=code, stdout=stdout, stderr=stderr
    )


def test_a_clean_run_says_nothing() -> None:
    build._refuse_if_the_solver_refused("t", _outcome(0))


def test_the_refusal_carries_the_solver_s_own_sentence() -> None:
    outcome = _outcome(
        1,
        stderr="Traceback (most recent call last):\n  File ...\n"
        "t: WINDOW_DAYS is still a placeholder. Measure the finished record.",
    )
    with pytest.raises(SystemExit, match="WINDOW_DAYS is still a placeholder"):
        build._refuse_if_the_solver_refused("t", outcome)


def test_the_last_line_wins_over_the_traceback_above_it() -> None:
    """A refusal is one sentence; the traceback above it is noise. Reporting
    the whole stream buries the sentence the reader needs."""

    outcome = _outcome(1, stderr="line one\nline two\nthe actual reason")
    with pytest.raises(SystemExit) as raised:
        build._refuse_if_the_solver_refused("t", outcome)
    assert "the actual reason" in str(raised.value)
    assert "line one" not in str(raised.value)


def test_a_silent_death_still_reports_something() -> None:
    """Guard the guard. A solver killed without writing anything must not
    produce an empty message — that reads as a build that passed."""

    with pytest.raises(SystemExit, match="exit status 137"):
        build._refuse_if_the_solver_refused("t", _outcome(137))


def test_stdout_is_used_when_stderr_is_empty() -> None:
    outcome = _outcome(1, stdout="printed the reason to stdout")
    with pytest.raises(SystemExit, match="printed the reason to stdout"):
        build._refuse_if_the_solver_refused("t", outcome)
