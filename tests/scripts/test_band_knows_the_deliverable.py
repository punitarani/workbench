"""A did-not-finish is not a zero, and the reader must be able to tell.

`band.py` exists to keep those apart. Its docstring says so outright:
averaged in as a zero, a DNF drags any task into the 0.2-0.8 band, so
"Opus 1.000 + Sol 0.600 + glm *nothing*" reads as 0.533 and looks like a
well-calibrated task.

The check that separates them asks whether the trial wrote the file the
task asked for. To ask that, the reader has to know the file's name — and
it looked for a line beginning `D =` in `grade.py`, which declares
`DELIVERABLE = criteria.DELIVERABLE`. It matched nothing, for every task
in the dataset, and returned None.

None was not inert. The caller guarded the check with `if wanted and ...`,
so a None turned it off entirely: a trial that wrote nothing fell through
to `reward.json`, which the verifier writes as 0.0 whatever happened.
**Every DNF was being averaged in as a zero** — the exact failure the
module was written to prevent, in the direction that flatters the result.

The second test here is the structural half and matters more than the
first. A reader that cannot identify the deliverable must stop. Returning
a falsy value let a broken lookup masquerade as "nothing to check".
"""

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "datasets" / "merrick" / "tasks"


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


band = _load("band")


def _live_tasks() -> list[str]:
    """The tasks a sweep would actually read.

    Retired ones are excluded the same way `band.py` excludes them, from
    the same marker — three tasks were withdrawn on measured evidence and
    left in place, and a reader that cannot tell them from live ones
    either reports tasks nobody runs or stops on one.
    """

    if not TASKS.is_dir():
        return []
    return sorted(
        p.name
        for p in TASKS.iterdir()
        if p.is_dir()
        and not p.name.startswith("_")
        and (p / "tests" / "criteria.py").is_file()
        and not band._retired(p)
    )


NAMED = _live_tasks()


def test_there_are_tasks_to_check() -> None:
    """Guard the guard: with no tasks the parametrised test below passes
    by having nothing to run."""

    assert NAMED, f"no tasks with criteria under {TASKS}"


@pytest.mark.parametrize("task", NAMED)
def test_the_deliverable_is_found_for_every_task(task: str) -> None:
    name = band._deliverable(TASKS, task)
    assert name and name.endswith(".json"), (
        f"{task}: the reader could not name the file the task asks for, so "
        "it cannot tell a trial that answered from one that did not"
    )


def test_a_task_naming_no_deliverable_stops_the_reader(tmp_path: Path) -> None:
    """The structural half. A lookup that fails must not read as 'no check
    needed' — that is how the original defect stayed invisible."""

    task = tmp_path / "nameless"
    (task / "tests").mkdir(parents=True)
    (task / "tests" / "criteria.py").write_text("ROWS = 'rows'\n")
    with pytest.raises(SystemExit):
        band._deliverable(tmp_path, "nameless")


def test_a_missing_criteria_file_stops_the_reader(tmp_path: Path) -> None:
    (tmp_path / "bare" / "tests").mkdir(parents=True)
    with pytest.raises(SystemExit):
        band._deliverable(tmp_path, "bare")


def _trial(root: Path, *, deliverable: str | None, reward: float | None) -> Path:
    trial = root / "trial-1"
    (trial / "verifier").mkdir(parents=True)
    (trial / "result.json").write_text("{}")
    if deliverable is not None:
        (trial / "verifier" / f"submitted-{deliverable}").write_text("{}")
    if reward is not None:
        (trial / "verifier" / "reward.json").write_text(json.dumps({"reward": reward}))
    return trial


def test_a_trial_that_wrote_nothing_is_not_a_zero(tmp_path: Path) -> None:
    """The recorded defect, from the direction it arrived: the verifier
    scores an absent answer 0.0, and that 0.0 must not become a score."""

    trial = _trial(tmp_path, deliverable=None, reward=0.0)
    value, why = band._outcome(trial, "answers.json")
    assert value is None, "a DNF was graded as 0.000"
    assert "deliverable" in why


def test_a_trial_that_answered_badly_is_a_zero(tmp_path: Path) -> None:
    """The other side. Excluding a real 0.0 would be the same error
    mirrored — 'timed out' and 'answered badly' call for opposite fixes."""

    trial = _trial(tmp_path, deliverable="answers.json", reward=0.0)
    value, why = band._outcome(trial, "answers.json")
    assert value == 0.0 and why == "ok"
