"""Rebuilding a task a sweep is reading destroys the measurement silently.

Harbor grades a trial when that trial finishes, against whatever
`tests/oracle.json` holds at that moment -- not against the key that was
there when the agent started reading. So a rebuild mid-sweep grades an
answer to the OLD brief with the NEW key.

It cost a real one. A kimi trial on `commitment-revision-register`
returned 26 rows and a superseded count of 127 against a true 128 -- a
good answer by any reading -- and scored 0.200, which is exactly the
empty-register floor, because `first_due` was added to the key while the
trial was still running. Its own instruction never mentioned the field.

Nothing reports that as anything but a low score, and no check after the
fact can find it: a contaminated trial is indistinguishable from a bad
one. The only place to catch it is before the build.
"""

import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "datasets" / "merrick"))

import build_tasks  # noqa: E402


class _Ran:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def _with_processes(monkeypatch, listing: str) -> None:
    monkeypatch.setattr(
        build_tasks.subprocess, "run", lambda *a, **k: _Ran(listing)
    )


SWEEPING = (
    "/usr/bin/python -u scripts/rollout.py --dataset merrick "
    "--task commitment-revision-register --model opus-5 --k 3\n"
    "/bin/zsh\n"
)


def test_it_refuses_a_task_a_sweep_is_reading(monkeypatch):
    _with_processes(monkeypatch, SWEEPING)
    with pytest.raises(SystemExit) as refused:
        build_tasks._refuse_while_a_sweep_is_reading(["commitment-revision-register"])
    message = str(refused.value)
    assert "commitment-revision-register" in message
    # The reason, not just the refusal: a reader who does not know WHY will
    # pass --force or delete the check.
    assert "old brief with the new key" in message


def test_it_allows_a_task_nobody_is_sweeping(monkeypatch):
    _with_processes(monkeypatch, SWEEPING)
    build_tasks._refuse_while_a_sweep_is_reading(["off-sense-register"])


def test_a_substring_of_another_task_name_does_not_trip_it(monkeypatch):
    """`--task commitment-revision-register` must not look like `...-register`."""

    _with_processes(monkeypatch, SWEEPING)
    build_tasks._refuse_while_a_sweep_is_reading(["revision-register"])


def test_building_everything_is_not_silently_exempt(monkeypatch):
    """No --task means build all, which includes whatever is being swept.

    Recorded as the known gap rather than left for someone to discover: the
    guard reads the task list it is given, and an empty list is "all
    tasks". This asserts the current behaviour so a change to it is
    deliberate.
    """

    _with_processes(monkeypatch, SWEEPING)
    build_tasks._refuse_while_a_sweep_is_reading([])


def test_a_broken_process_listing_does_not_block_a_build(monkeypatch):
    """The guard is a courtesy. It must never be the reason a build fails."""

    def explode(*_a, **_k):
        raise OSError("no ps here")

    monkeypatch.setattr(build_tasks.subprocess, "run", explode)
    build_tasks._refuse_while_a_sweep_is_reading(["commitment-revision-register"])
