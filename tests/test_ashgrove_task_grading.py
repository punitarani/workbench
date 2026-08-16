"""A task's grader must accept its own oracle, and must grade all of it.

Two failures cost a real measurement before these guards existed. The
close-out grader kept a hand-written copy of the deliverable's field set,
so the day the report grew `wip_at_risk_dollars` every correct answer
failed the schema check. The same change added `wip_dollars` to every
row and never added it to the graded spec, so the field the task was
hardened around earned neither credit nor penalty.

Both are invisible from a score alone — the run still produces a number,
it is just measuring something other than what the task claims.

rewardkit lives in the Harbor verifier image, not this venv, so the
grading scripts are executed against a recording stub: what matters here
is which fields each script asks to be graded, not what the criteria
compute.
"""

import ast
import json
import sys
import types
from pathlib import Path

import pytest

TASKS = sorted(p for p in (Path("datasets/ashgrove/tasks")).iterdir() if p.is_dir())


def _stub(calls: list) -> types.ModuleType:
    """A stand-in for rewardkit that records every criterion registration."""

    module = types.ModuleType("rewardkit")

    def criterion(*_args, **_kwargs):
        return lambda fn: fn

    def __getattr__(name: str):
        def record(*args, **kwargs):
            calls.append((name, args, kwargs))

        return record

    module.criterion = criterion
    module.__getattr__ = __getattr__
    return module


def _run(path: Path, calls: list) -> dict:
    """Execute a grading script under the stub and return its namespace."""

    sys.modules["rewardkit"] = _stub(calls)
    try:
        namespace: dict = {"__file__": str(path), "__name__": path.stem}
        exec(compile(path.read_text(), str(path), "exec"), namespace)
        return namespace
    finally:
        del sys.modules["rewardkit"]


def _oracle(task: Path) -> dict:
    return json.loads((task / "tests/oracle.json").read_text())


def _answer_scripts(task: Path) -> list[Path]:
    """Tasks name their answer script for the task, not `grade.py`."""

    return sorted((task / "tests/answer").glob("*.py"))


def _row_lists(oracle: dict) -> list[list[dict]]:
    """Every table the report publishes — some tasks publish more than one."""

    return [
        value
        for value in oracle.values()
        if isinstance(value, list) and value and isinstance(value[0], dict)
    ]


def _names(value, into: set) -> None:
    """Every field name the grading calls and criteria constants mention."""

    if isinstance(value, dict):
        into.update(k for k in value if isinstance(k, str))
        for item in value.values():
            _names(item, into)
    elif isinstance(value, (set, frozenset)):
        into.update(v for v in value if isinstance(v, str))
    elif isinstance(value, (list, tuple)):
        for item in value:
            _names(item, into)
    elif isinstance(value, str):
        into.add(value)


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_every_criterion_called_is_defined(task: Path) -> None:
    """`rk.name(...)` must resolve to a criterion this task defines.

    rewardkit exposes shared criteria as module attributes and raises
    AttributeError for anything else, so a grading script that calls a
    criterion under a name nobody defined does not score badly — it fails
    to import, the verifier writes no reward file, and Harbor reports
    RewardFileNotFoundError after a full agent rollout has been paid for.

    That is what a renamed task cost here: two tasks kept calling
    `rk.flagged_f1` while their criteria still defined `undelivered_f1`
    and `id_set_f1`. Twenty-one minutes of rollout, no measurement. The
    other guards in this file check what is graded; this one checks that
    grading can run at all.
    """

    defined = {
        node.name
        for node in ast.walk(ast.parse((task / "tests/criteria.py").read_text()))
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    for script in (*_answer_scripts(task), *(task / "tests/process").glob("*.py")):
        called = {
            node.func.attr
            for node in ast.walk(ast.parse(script.read_text()))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "rk"
        }
        missing = sorted(called - defined)
        assert not missing, (
            f"{task.name}: {script.name} calls {missing} but criteria.py "
            f"defines only {sorted(defined)}"
        )


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_schema_check_matches_the_oracle(task: Path) -> None:
    """The required field set must be the oracle's, not a copy of it."""

    criteria = _run(task / "tests/criteria.py", [])
    declared = {
        name: set(value)
        for name, value in criteria.items()
        if name.startswith("TOP") and isinstance(value, (set, frozenset))
    }
    assert declared, f"{task.name}: no top-level field set found in criteria.py"
    for name, fields in declared.items():
        assert fields == set(_oracle(task)), (
            f"{task.name}: {name} does not match the oracle's fields; "
            f"only in {name}: {sorted(fields - set(_oracle(task)))}, "
            f"only in oracle: {sorted(set(_oracle(task)) - fields)}"
        )


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_every_published_field_is_graded(task: Path) -> None:
    """A field the report publishes but nothing grades is not a task."""

    oracle = _oracle(task)
    calls: list = []
    criteria = _run(task / "tests/criteria.py", calls)
    for script in _answer_scripts(task):
        _run(script, calls)

    # The expected values are handed to the grader straight off the oracle,
    # so harvesting names from them would find every field by construction
    # and prove nothing. Only what the script asks for counts.
    expected = list(oracle.values())

    # Some graders name their fields in a spec dict the script passes, others
    # inside the criterion body. Both count, so read the criteria source too:
    # a field named nowhere in the grading code is certainly not graded.
    graded: set = {
        node.value
        for node in ast.walk(ast.parse((task / "tests/criteria.py").read_text()))
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }
    for name, args, kwargs in calls:
        _names(name, graded)
        for value in list(args) + list(kwargs.values()):
            if any(value is want or value == want for want in expected):
                continue
            _names(value, graded)
    for name, value in criteria.items():
        if name.isupper() and isinstance(value, (set, frozenset)):
            _names(value, graded)

    missing = sorted(key for key in oracle if key not in graded)
    assert not missing, f"{task.name}: published but never graded: {missing}"

    # A row's identifier is graded by the matching itself — rows are looked
    # up by it — so it is not expected in a field spec. Solvers put it first;
    # graders that name it say so in KEY.
    for rows in _row_lists(oracle):
        key = criteria.get("KEY") or next(iter(rows[0]))
        ungraded = sorted(f for f in rows[0] if f != key and f not in graded)
        assert not ungraded, f"{task.name}: row fields never graded: {ungraded}"
