"""A task that declares criteria but never invokes them scores nothing.

Every task in this dataset shipped a `criteria.py` naming its rows, its key
and its graded fields, and a `criteria_base.py` holding the criterion bodies
behind `@criterion(shared=True)`. **Nothing called them.**

Declaring and registering are different acts. The decorator makes
`rk.row_f1(...)` available; something has to invoke it with the task's own
oracle before Reward Kit has a reward to compute. Run against the real
discovery, a task with only declarations returns **zero** rewards — and an
empty reward set is written out as `{}` and read downstream as a score,
so every trial of every model would have come back with nothing, for
reasons no model had any part in. It went unnoticed because the sibling
dataset that does work keeps its invocation in files this one never had:
`tests/answer/`, `tests/process/` and `tests/test.sh`.

This exercises the shipped invocation the way Reward Kit will: it registers
the criteria against a synthetic oracle in the task's own shape and asserts
that something was registered, that every call binds to the criterion it
names, and that the row criteria are among them.
"""

import json
import sys
import tomllib
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATASET = REPO / "datasets" / "merrick"
GRADING = DATASET / "grading"

sys.path.insert(0, str(REPO / "tests"))
import rewardkit_stub  # noqa: E402


def _live() -> list[Path]:
    out = []
    for task in sorted((DATASET / "tasks").glob("*/")):
        solver = task / "solution" / "solve.py"
        if not solver.is_file() or task.name.startswith("_"):
            continue
        if solver.read_text(encoding="utf-8").lstrip().startswith('"""RETIRED'):
            continue
        out.append(task)
    return out


TASKS = _live()


def test_the_audit_found_tasks_to_check() -> None:
    assert TASKS, "no live merrick tasks"


def test_the_invocation_layer_exists_to_be_shipped() -> None:
    """The three files whose absence caused this. Checked once, not per task,
    because the build copies these into every task."""

    for name in ("grade.py", "method.py", "test.sh"):
        assert (GRADING / name).is_file(), (
            f"datasets/merrick/grading/{name} is missing — without it no task "
            "registers any criterion and every trial returns no score"
        )


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_criteria_names_the_deliverable_its_manifest_declares(task: Path) -> None:
    """`grade.py` reads the deliverable's name off `criteria.py`. If that
    disagrees with the manifest, every criterion grades a file the agent was
    never asked to write — which scores zero while looking like a model that
    produced nothing."""

    manifest = tomllib.loads((task / "task.toml").read_text(encoding="utf-8"))
    declared = manifest["metadata"]["evidence"]["primary_field"]
    criteria_src = (task / "tests" / "criteria.py").read_text(encoding="utf-8")
    assert f'DELIVERABLE = "{declared}"' in criteria_src, (
        f"{task.name}: task.toml names {declared!r} as the deliverable and "
        "tests/criteria.py does not declare it"
    )


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_the_shipped_invocation_registers_criteria(task: Path, tmp_path: Path) -> None:
    """Run the invocation the way Reward Kit will, and require rewards.

    The oracle is synthesised in the task's own shape rather than read,
    because these tasks are staged and none has one yet — and the defect this
    guards is present with or without real values.
    """

    criteria_src = task / "tests" / "criteria.py"
    staged = tmp_path / "tests"
    (staged / "answer").mkdir(parents=True)
    (staged / "process").mkdir()
    for source, destination in (
        (criteria_src, staged / "criteria.py"),
        (DATASET / "criteria_base.py", staged / "criteria_base.py"),
        (GRADING / "grade.py", staged / "answer" / "grade.py"),
        (GRADING / "method.py", staged / "process" / "method.py"),
    ):
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    # Read the module's constants without importing the criterion bodies:
    # drop the one shared-import line and exec the rest. Splitting *at* that
    # line loses everything after it, which is where the constants live.
    prologue = "\n".join(
        line
        for line in criteria_src.read_text(encoding="utf-8").splitlines()
        if not line.startswith("from criteria_base import")
    )
    namespace: dict = {"__file__": str(criteria_src)}
    exec(compile(prologue, str(criteria_src), "exec"), namespace)  # noqa: S102
    rows, key, fields = namespace["ROWS"], namespace["KEY"], namespace["FIELDS"]
    oracle = {
        "window_end": "2026-01-20",
        "counted": 1,
        rows: [{**{k: "x" for k in key}, **{f: "y" for f in fields}}],
    }
    (staged / "oracle.json").write_text(json.dumps(oracle), encoding="utf-8")

    calls: list = []
    sys.modules["rewardkit"] = rewardkit_stub.registering(calls)
    sys.path.insert(0, str(staged))
    try:
        for part in ("answer/grade.py", "process/method.py"):
            source = staged / part
            exec(
                compile(source.read_text(encoding="utf-8"), str(source), "exec"),
                {"__file__": str(source)},
            )  # noqa: S102
    finally:
        sys.path.remove(str(staged))
        for name in ("rewardkit", "criteria", "criteria_base"):
            sys.modules.pop(name, None)

    assert calls, (
        f"{task.name}: the shipped invocation registered no criteria at all. "
        "Reward Kit writes an empty reward set for this, which reads "
        "downstream as a score rather than as a failure."
    )
    names = {c[0] for c in calls}
    assert {"row_f1", "row_fields", "schema_ok"} <= names, (
        f"{task.name}: registered {sorted(names)} — the row set, the per-row "
        "facts and the deliverable's shape must all be graded"
    )
