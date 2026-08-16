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
import inspect
import json
import re
import sys
import types
from pathlib import Path

import pytest

TASKS = sorted(p for p in (Path("datasets/ashgrove/tasks")).iterdir() if p.is_dir())


def _stub(calls: list) -> types.ModuleType:
    """A stand-in for rewardkit that registers criteria the way it does.

    Faithful on purpose. A permissive stub — one that accepts any name
    with any arguments — passes every grading script ever written, and
    three separate rollouts were spent discovering what it would have
    caught in a second: a criterion called under a name nobody defined,
    a call carrying one more positional argument than the criterion
    takes, and a description template naming a parameter that had been
    removed. Each is an import-time death in the verifier, so Harbor
    reports RewardFileNotFoundError rather than a score, and the run is
    paid for in full before anyone learns anything.

    So this mimics the three things rewardkit does at registration:
    resolve the name against the shared criteria, bind the caller's
    arguments to the signature (less `workspace`, which the runner
    injects), and format the description against that binding.
    """

    module = types.ModuleType("rewardkit")
    registered: dict[str, tuple] = {}

    def criterion(*_args, description: str | None = None, **_kwargs):
        def decorate(fn):
            registered[fn.__name__] = (fn, description)
            return fn

        return decorate

    def __getattr__(name: str):
        if name not in registered:
            raise AttributeError(f"module 'rewardkit' has no attribute {name!r}")
        fn, description = registered[name]
        signature = inspect.Signature(
            [
                parameter
                for parameter in inspect.signature(fn).parameters.values()
                if parameter.name != "workspace"
            ]
        )

        def register(*args, **kwargs):
            own = {k: v for k, v in kwargs.items() if k not in ("name", "weight")}
            bound = signature.bind_partial(*args, **own)
            if description:
                description.format(**{**kwargs, **bound.arguments})
            calls.append((name, args, kwargs))

        return register

    module.criterion = criterion
    module.__getattr__ = __getattr__
    module.registered = registered
    return module


def _exec(path: Path, namespace: dict | None = None) -> dict:
    namespace = namespace or {"__file__": str(path), "__name__": path.stem}
    namespace |= {"__file__": str(path), "__name__": path.stem}
    exec(compile(path.read_text(), str(path), "exec"), namespace)
    return namespace


def _run(path: Path, calls: list) -> dict:
    """Execute one grading file against a stub that knows nothing yet."""

    sys.modules["rewardkit"] = _stub(calls)
    try:
        return _exec(path)
    finally:
        del sys.modules["rewardkit"]


def _load(task: Path) -> tuple[dict, list, dict]:
    """Criteria namespace, the calls its scripts made, and the functions."""

    calls: list = []
    module = _stub(calls)
    sys.modules["rewardkit"] = module
    try:
        criteria = _exec(task / "tests/criteria.py")
        for script in (*_answer_scripts(task), *(task / "tests/process").glob("*.py")):
            _exec(script)
    finally:
        del sys.modules["rewardkit"]
    return criteria, calls, module.registered


def _run_task(task: Path, calls: list) -> dict:
    """Load a task's criteria and then its scripts, sharing one module.

    The verifier imports criteria.py and the grading scripts into the
    same rewardkit, which is the whole reason `rk.name(...)` resolves at
    all. Giving each file its own stub hid that: the scripts ran against
    an empty registry and every name looked fine because nothing was
    ever checked.
    """

    sys.modules["rewardkit"] = _stub(calls)
    try:
        criteria = _exec(task / "tests/criteria.py")
        for script in (*_answer_scripts(task), *(task / "tests/process").glob("*.py")):
            _exec(script)
        return criteria
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
        node.name: node.args
        for node in ast.walk(ast.parse((task / "tests/criteria.py").read_text()))
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
    }
    for script in (*_answer_scripts(task), *(task / "tests/process").glob("*.py")):
        calls = [
            node
            for node in ast.walk(ast.parse(script.read_text()))
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "rk"
        ]
        missing = sorted({c.func.attr for c in calls} - set(defined))
        assert not missing, (
            f"{task.name}: {script.name} calls {missing} but criteria.py "
            f"defines only {sorted(defined)}"
        )
        # Arity too. rewardkit binds these itself and a mismatch is the
        # same import-time death as a missing name: this task was copied
        # from a criteria.py whose `scalar` took no tolerance, and every
        # `rk.scalar(D, field, expected, 0.02)` in it raised "too many
        # positional arguments" before a single criterion could run.
        for call in calls:
            args = defined[call.func.attr]
            # `workspace` is injected by the runner, `name` and `weight`
            # are the registration's own; what is left is the caller's.
            allowed = len(args.posonlyargs) + len(args.args) - 1
            required = allowed - len(args.defaults)
            given = len(call.args)
            assert required <= given <= allowed, (
                f"{task.name}: {script.name} calls rk.{call.func.attr} with "
                f"{given} positional argument(s); criteria.py accepts "
                f"{required}..{allowed}"
            )


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_criterion_descriptions_name_real_parameters(task: Path) -> None:
    """A `{placeholder}` in a description must be one of the arguments.

    rewardkit formats the description against the bound call, so a
    template naming a parameter the function no longer takes raises
    KeyError at registration — again at import, again no reward file,
    again after the rollout is paid for. This is the third shape of the
    same accident: `flagged_f1` replaced an `id_set_f1` that took a
    `field`, the decorator above it kept saying `{field} set, F1 against
    the truth`, and eleven minutes of agent produced no number.
    """

    tree = ast.parse((task / "tests/criteria.py").read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        parameters = {a.arg for a in (*node.args.posonlyargs, *node.args.args)}
        parameters |= {a.arg for a in node.args.kwonlyargs}
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            for keyword in decorator.keywords:
                if keyword.arg != "description":
                    continue
                if not isinstance(keyword.value, ast.Constant):
                    continue
                named = set(re.findall(r"{(\w+)}", str(keyword.value.value)))
                unknown = sorted(named - parameters)
                assert not unknown, (
                    f"{task.name}: {node.name}'s description names "
                    f"{unknown}, which it does not take; it takes "
                    f"{sorted(parameters)}"
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
    criteria = _run_task(task, calls)

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


@pytest.mark.parametrize("task", TASKS, ids=lambda p: p.name)
def test_the_oracle_scores_full_marks(task: Path, tmp_path: Path) -> None:
    """Hand the grader the reference answer; it must score every point.

    This is the property the whole dataset rests on. If the oracle does
    not score 1.0 against its own criteria, then some part of the gap an
    agent is charged for belongs to the task, and the standing rule —
    every lost point is a defect until the transcript says otherwise —
    cannot be applied to anything.

    It is also the only check here that runs the criteria rather than
    registering them. Two rollouts were spent on bugs living in criterion
    bodies rather than their signatures: a composite row key left
    unpatched in three of five places, so `row[('person', 'engagement')]`
    raised KeyError, and `_rows` keying every one of a hundred and
    ninety-seven rows to the string "None".
    """

    criteria, calls, registered = _load(task)
    oracle = _oracle(task)
    for name, args, _kwargs in calls:
        deliverable = tmp_path / str(args[0])
        deliverable.parent.mkdir(parents=True, exist_ok=True)
        deliverable.write_text(json.dumps(oracle, indent=1) + "\n")
        function, _description = registered[name]
        score = float(function(tmp_path, *args))
        assert score == 1.0, (
            f"{task.name}: criterion {name} scores {score:.3f} on the "
            f"oracle itself — the reference answer cannot get full marks, "
            f"so neither can any agent"
        )
