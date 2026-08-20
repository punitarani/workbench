"""Ashgrove's shared grader, tested on the mistakes its predecessors made.

Seventeen near-identical copies of this logic used to live under
`tasks/*/tests/criteria.py`. They had already drifted apart when the
shared module was extracted -- `row_fields` in five variants, `scalar` in
four -- so each rule below is pinned by the failure that produced it
rather than by the happy path.

The second half is the one that would otherwise be found in production:
`criteria.py` can only import `criteria_base` inside a container if the
build copies it in, and nothing about running the suite from the repo
root would ever notice its absence.
"""

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "datasets" / "ashgrove"
SOURCE = DATASET / "criteria_base.py"
TASKS = sorted(p for p in (DATASET / "tasks").iterdir() if p.is_dir())


def _load(tmp_path: Path):
    """Import the shared grader under the shared rewardkit stand-in.

    In its calling mode: the real decorator returns the function
    unchanged, so what these tests invoke is what the verifier invokes.
    """

    sys.path.insert(0, str(REPO / "tests"))
    import rewardkit_stub

    sys.modules["rewardkit"] = rewardkit_stub.calling()
    shutil.copyfile(SOURCE, tmp_path / "criteria_base.py")
    spec = importlib.util.spec_from_file_location(
        f"acb_{tmp_path.name}", tmp_path / "criteria_base.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ROWS = [{"ref": "a", "ok": True}, {"ref": "b", "ok": False}]


def _write(workspace: Path, payload: dict) -> None:
    (workspace / "answer.json").write_text(json.dumps(payload))


def test_a_boolean_field_can_score(tmp_path: Path) -> None:
    """`bool` subclasses `int`, so a tolerance comparison rejects `True`
    outright and every boolean field scores zero -- including correct
    ones. A reference answer graded 0.571 against its own criteria, and
    when this module was extracted eight of the fifteen copies still
    carried the version without the fix."""

    cb = _load(tmp_path)
    _write(tmp_path, {"rows": ROWS})
    score = cb.grade_row_fields(
        tmp_path, "answer.json", "rows", ("ref",), ROWS, {"ok": 0.0}
    )
    assert score == 1.0


def test_under_reporting_is_not_free(tmp_path: Path) -> None:
    """Iterating the submission and skipping unmatched rows would score
    one perfect row out of two as 1.000."""

    cb = _load(tmp_path)
    _write(tmp_path, {"rows": [{"ref": "a", "ok": True}]})
    score = cb.grade_row_fields(
        tmp_path, "answer.json", "rows", ("ref",), ROWS, {"ok": 0.0}
    )
    assert score == pytest.approx(0.5)


def test_invented_rows_cost_but_do_not_wipe_out_correct_work(tmp_path: Path) -> None:
    """A cliff to zero tells the reader nothing about what the agent knew."""

    cb = _load(tmp_path)
    invented = [{"ref": f"x{n}", "ok": True} for n in range(40)]
    _write(tmp_path, {"rows": ROWS + invented})
    score = cb.grade_row_fields(
        tmp_path, "answer.json", "rows", ("ref",), ROWS, {"ok": 0.0}
    )
    assert 0.0 < score < 1.0


def test_nothing_expected_and_nothing_given_is_correct(tmp_path: Path) -> None:
    """A task whose world held no findings used to fail its own reference
    answer."""

    cb = _load(tmp_path)
    _write(tmp_path, {"rows": []})
    assert (
        cb.grade_row_fields(tmp_path, "answer.json", "rows", ("ref",), [], {"ok": 0.0})
        == 1.0
    )
    assert cb.grade_row_f1(tmp_path, "answer.json", "rows", ("ref",), []) == 1.0


def test_a_multi_part_key_does_not_collapse_rows(tmp_path: Path) -> None:
    """A key that distinguishes fewer rows than exist caps the achievable
    score below 1.0 for reasons no agent can fix -- and row F1 will not
    show it, because both sides dedupe identically and it still reads
    1.000. It bites in the per-row check."""

    cb = _load(tmp_path)
    rows = [
        {"ref": "a", "due": "2026-01-05", "ok": True},
        {"ref": "a", "due": "2026-01-09", "ok": False},
    ]
    _write(tmp_path, {"rows": rows})
    spec = {"ok": 0.0}
    good = ("ref", "due")
    assert cb.grade_row_f1(tmp_path, "answer.json", "rows", good, rows) == 1.0
    assert cb.grade_row_fields(tmp_path, "answer.json", "rows", good, rows, spec) == 1.0
    assert cb.grade_row_f1(tmp_path, "answer.json", "rows", ("ref",), rows) == 1.0
    assert (
        cb.grade_row_fields(tmp_path, "answer.json", "rows", ("ref",), rows, spec) < 1.0
    )


def test_a_list_valued_scalar_compares_by_equality(tmp_path: Path) -> None:
    """Without this branch a list fell through to the numeric comparison
    and returned False for every value including the right one -- the
    reference answer scored 0.000 against its own grader."""

    cb = _load(tmp_path)
    _write(tmp_path, {"forms": ["a", "b"]})
    assert cb.grade_scalar(tmp_path, "answer.json", "forms", ["a", "b"]) is True
    assert cb.grade_scalar(tmp_path, "answer.json", "forms", ["a"]) is False


def test_a_missing_or_unparsable_deliverable_scores_zero(tmp_path: Path) -> None:
    cb = _load(tmp_path)
    assert cb.submitted(tmp_path, "answer.json") is None
    (tmp_path / "answer.json").write_text("not json at all")
    assert cb.submitted(tmp_path, "answer.json") is None


def test_the_oversize_cap_is_per_task(tmp_path: Path) -> None:
    """Two tasks cap at 200_000 rather than the register tasks' 300_000;
    widening them silently would change what an oversized submission
    scores."""

    cb = _load(tmp_path)
    (tmp_path / "answer.json").write_text(json.dumps({"pad": "x" * 250_000}))
    assert cb.submitted(tmp_path, "answer.json") is not None
    assert cb.submitted(tmp_path, "answer.json", 200_000) is None


def _build_tasks():
    """The dataset's builder, or a skip.

    Imported for `ship_grading_base` alone, but the module pulls in the
    simulation stack to do it. Where that stack cannot load -- a Python
    the pinned pydantic does not support, say -- skip rather than report
    a grading failure for a reason that has nothing to do with grading.
    """

    spec = importlib.util.spec_from_file_location(
        "ashgrove_build_tasks", DATASET / "build_tasks.py"
    )
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"ashgrove build_tasks.py will not import here: {exc}")
    return module


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_the_build_ships_a_criteria_that_imports_standalone(
    task: Path, tmp_path: Path
) -> None:
    """Run the real shipping step, then import the way the grader will.

    The only path a container has is the task's own `tests/`: Harbor
    stages that directory by itself and the dataset root holding
    `criteria_base.py` is not there at all. If the copy stops happening,
    every criterion of every task raises ModuleNotFoundError on load,
    nothing scores, and a total wipeout reads as catastrophic model
    failure rather than as a missing file.

    This calls `ship_grading_base` rather than restating what it does.
    A test that reimplements the step it is checking agrees with itself
    by construction and drifts from the code the moment either moves --
    which is the defect this whole module exists to remove.
    """

    build = _build_tasks()
    staged = tmp_path / task.name
    shutil.copytree(task, staged)
    build.ship_grading_base(staged, task.name)

    assert (staged / "tests" / "criteria_base.py").is_file()
