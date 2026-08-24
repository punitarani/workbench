"""Printing a floor is not checking it.

`build_tasks` has measured and printed each task's no-comprehension floors
for months, on the reasoning that "a rollout number is never read without
it". Printing was the whole of it. Nothing compared the number to a
threshold, so a task could pay a dump 0.95 and announce it in the build log
on its way to shipping.

That is not hypothetical. Ashgrove -- a shipped dataset, banded across
three models -- pays a dump 0.990 on `client-responsiveness-sla` and 0.954
on `workpaper-open-items`, and six of its fifteen keyed tasks state no
count of what they read, so no dump floor exists for them at all. Under
this gate, **10 of its 17 tasks refuse and the other 7 warn**; not one
passes clean. Merrick's own tasks measure 0.363-0.556 and pass silently,
which is the other half of the check: a gate that refuses everything is
worth as little as one that refuses nothing.

The two refusals are ordered deliberately. The missing-floor case hides the
high-floor case: a task with no candidate count produces no dump floor,
prints one quiet line, and reads as fine. Absence is the failure mode that
survives, because it produces no error and no wrong number -- only a
question nobody asks.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from dataset_modules import dataset_module

B = dataset_module("merrick", "baselines")
REPO = Path(__file__).resolve().parents[2]


def _floors(**kwargs: float) -> dict[str, float]:
    return {"empty_register": 0.2, "no_work_at_all": 0.0, **kwargs}


def test_no_floors_at_all_is_refused() -> None:
    with pytest.raises(SystemExit, match="no floors could be measured"):
        B.refuse_a_task_a_dump_can_pass("t", {})


def test_an_unmeasurable_dump_is_refused() -> None:
    """The case that hides the others, and the one that reads as fine."""

    floors = _floors(**{B.UNMEASURABLE: float("nan")})
    with pytest.raises(SystemExit, match="no count of what was read"):
        B.refuse_a_task_a_dump_can_pass("t", floors)


def test_a_dump_at_the_top_of_the_band_is_refused() -> None:
    with pytest.raises(SystemExit, match="0.954"):
        B.refuse_a_task_a_dump_can_pass("t", _floors(reported_every_candidate=0.954))


def test_the_ceiling_is_the_band_it_names() -> None:
    """Exactly at the threshold refuses; a hair under does not.

    `>=` rather than `>` because a dump landing exactly on the top of the
    target band is already inside every score the task can report.
    """

    with pytest.raises(SystemExit):
        B.refuse_a_task_a_dump_can_pass(
            "t", _floors(reported_every_candidate=B.DUMP_CEILING)
        )
    B.refuse_a_task_a_dump_can_pass(
        "t", _floors(reported_every_candidate=B.DUMP_CEILING - 0.001)
    )


def test_the_middle_warns_and_does_not_refuse(capsys: pytest.CaptureFixture) -> None:
    B.refuse_a_task_a_dump_can_pass("t", _floors(reported_every_candidate=0.70))
    out = capsys.readouterr().out
    assert "WARNING" in out and "0.700" in out
    assert "0.300 of the scale is above it" in out, out


def test_a_low_floor_raises_no_warning(capsys: pytest.CaptureFixture) -> None:
    B.refuse_a_task_a_dump_can_pass("t", _floors(reported_every_candidate=0.44))
    assert "WARNING" not in capsys.readouterr().out


def test_every_measurable_floor_says_what_it_cannot_see(
    capsys: pytest.CaptureFixture,
) -> None:
    """The caveat is unconditional, and a low floor is where it matters most.

    The dump is sized from the candidate count the report declares, so a
    task that declares a generous pool measures a *better* floor while
    being easier to dump -- a reader who cheaply narrows the pool first
    submits fewer, better rows than the baseline does. Measured on
    deadline-week-promise-clock: 158 promises against 707 messages reads
    0.365, against the 332 carrying any relative date it reads 0.645, and
    the second is the set a dumper would actually submit.

    An earlier version of this file asserted that a low floor prints
    nothing at all, which is exactly the reading the caveat exists to
    prevent -- silence on the number that most needs the qualification.
    """

    for floor in (0.10, 0.44, 0.70):
        B.refuse_a_task_a_dump_can_pass("t", _floors(reported_every_candidate=floor))
        assert "DECLARED candidate" in capsys.readouterr().out, floor


def test_the_thresholds_are_ordered() -> None:
    assert 0.0 < B.DUMP_WARN < B.DUMP_CEILING <= 1.0


@pytest.mark.parametrize(
    "task",
    sorted(
        p.name
        for p in (REPO / "datasets/merrick/tasks").iterdir()
        if (p / "tests" / "oracle.json").is_file()
    ),
)
def test_this_dataset_s_own_tasks_pass_it(
    task: str, capsys: pytest.CaptureFixture
) -> None:
    """A gate the dataset it guards cannot pass is not a gate, it is a wall.

    These run for real -- they are the only assurance that the thresholds
    were set against measured tasks rather than chosen to look strict.
    """

    path = REPO / "datasets/merrick/tasks" / task
    floors = B.measure(path, json.loads((path / "tests" / "oracle.json").read_text()))
    B.refuse_a_task_a_dump_can_pass(task, floors)
    assert "WARNING" not in capsys.readouterr().out, (
        f"{task} is close enough to its dump floor to warn"
    )
