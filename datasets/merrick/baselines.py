"""What a task scores for answers that demonstrate nothing.

A band is only meaningful against a floor. Measured on the real grading
path with this dataset's own shape — a 20-row register drawn from 241
candidates — three answers that involve no comprehension at all score:

    empty register, scalars correct           0.200
    empty register, only the brief's window   0.100
    every candidate reported (recall 1.0)     0.427

All three sit inside the 0.2–0.8 band this dataset targets. A model
scoring 0.43 on such a task may have read every message carefully or may
have dumped the candidate list, and **the number does not distinguish
them**. That is not a grading bug — the ordering is right, a careful
partial reader who found half the rows and invented nothing scores 0.683,
comfortably above the dumper — but a band judgement made without the
floor is a judgement made on half the evidence.

Where the dump floor comes from, since the temptation is to "fix" it:

    scalars                     0.200   the brief states one of the two
    row_fields' capped penalty  0.150   min(extra * fields, checked // 2)
    row_f1                      0.077   precision 0.083, recall 1.000

The cap is deliberate and documented in `criteria_base`: a wrong answer
must not wipe out work that was right, because a cliff to zero says
nothing about what the agent knew. It also means `row_fields` cannot fall
below 0.5 however much noise is added. Both facts are true at once. The
answer is to *report* the floor, not to re-tune a penalty whose reason
still holds.

Nothing here reimplements grading. Each baseline is written to a scratch
workspace and scored by running the task's own `test.sh`, which is the
entry point a trial uses — so a baseline cannot drift from the thing it
is a baseline for.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

# A row the register would never legitimately contain, repeated. The
# content does not matter; only that its key misses every truth key.
_NOISE_KEY_PREFIX = "baseline-noise-"


def _noise_rows(
    count: int, key: tuple[str, ...], fields: tuple[str, ...]
) -> list[dict]:
    rows = []
    for index in range(max(0, count)):
        row = {name: f"{_NOISE_KEY_PREFIX}{index}" for name in key}
        row.update({name: "" for name in fields if name not in key})
        rows.append(row)
    return rows


def _score(tests_dir: Path, deliverable: str, answer: dict) -> float | None:
    """Run the task's own verifier over one answer and read the reward."""

    # Resolved, because this runs the script with `cwd` set to the task
    # directory: a relative `tests_dir` then resolves against the task
    # rather than the repository and `sh` exits 127. The build always
    # passes absolute paths, so the failure only appears when somebody
    # calls this by hand — and it appears as "baselines could not be
    # measured", which reads like a broken task rather than a broken call.
    tests_dir = tests_dir.resolve()
    with tempfile.TemporaryDirectory() as scratch:
        workspace = Path(scratch) / "workspace"
        logs = Path(scratch) / "logs"
        workspace.mkdir()
        logs.mkdir()
        (workspace / deliverable).write_text(json.dumps(answer), encoding="utf-8")
        result = subprocess.run(
            ["sh", str(tests_dir / "test.sh")],
            cwd=tests_dir.parent,
            env={
                **os.environ,
                "WORKBENCH_WORKSPACE": str(workspace),
                "VERIFIER_LOG_DIR": str(logs),
            },
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None
        reward = logs / "reward.json"
        if not reward.is_file():
            return None
        return float(json.loads(reward.read_text())["reward"])


def measure(task: Path, oracle: dict) -> dict[str, float]:
    """The floors this task's band must be read against.

    Everything it needs comes from the task's own `criteria.py` and
    `oracle.json`, so a call site cannot pass one task's row key while
    grading another's answer.

    `candidates` is taken from the task's own count-of-what-was-read
    scalar, whichever one that is: an answer reporting every candidate is
    the strongest no-comprehension strategy available, and the task itself
    is what says how many candidates there were.
    """

    tests = task / "tests"
    criteria_path = tests / "criteria.py"
    if not (tests / "test.sh").is_file() or not criteria_path.is_file():
        return {}
    deliverable = _deliverable_of(criteria_path)
    rows_key = _literal_of(criteria_path, "ROWS")
    key = _literal_of(criteria_path, "KEY") or ()
    fields = tuple(_literal_of(criteria_path, "FIELDS") or ())
    if deliverable is None or not rows_key:
        return {}

    truth = oracle.get(rows_key) or []
    scalars = {k: v for k, v in oracle.items() if not isinstance(v, list)}
    # The largest `*_read` count, by name-sorted order for a stable choice
    # when a task reports more than one. Taking whichever came first in the
    # oracle's dict would make this floor depend on JSON key order, which
    # is exactly the kind of number that changes without anyone editing it.
    read_counts = sorted(
        (int(v) for k, v in sorted(scalars.items()) if k.endswith("_read")),
        reverse=True,
    )
    candidates = read_counts[0] if read_counts else len(truth)

    floors: dict[str, float] = {}
    empty_with_scalars = _score(tests, deliverable, {**scalars, rows_key: []})
    if empty_with_scalars is not None:
        floors["empty_register"] = empty_with_scalars

    # What a reader who did no work can still fill in: the fields whose
    # values the brief states. Everything else is left wrong on purpose.
    restated = _restated_of(criteria_path)
    trivial = {
        name: (value if name in restated else _wrong(value))
        for name, value in scalars.items()
    }
    no_work = _score(tests, deliverable, {**trivial, rows_key: []})
    if no_work is not None:
        floors["no_work_at_all"] = no_work

    # Two figures, because one of them flatters and the other is bleak, and
    # the truth is between them.
    #
    # Handing the dump the oracle's scalars assumes a reader who reports
    # every candidate as a row somehow knows the true counts anyway. That
    # is an upper bound, and on one task it read 0.587 — an alarming
    # number that is partly the baseline's own generosity. A reader who
    # dumps reports counts consistent with their dump and gets them wrong,
    # which is the lower bound.
    #
    # Neither is the answer on its own. A wide gap between them says the
    # scalars carry a large share of the reward, which is itself worth
    # seeing: on that same task six scalars were 43% of the weight and
    # five of the six were derivable from the row set the task already
    # grades.
    dump_rows = list(truth) + _noise_rows(
        candidates - len(truth), tuple(key), tuple(fields)
    )
    bleak = _score(
        tests,
        deliverable,
        {
            **{name: _wrong(value) for name, value in scalars.items()},
            rows_key: dump_rows,
        },
    )
    if bleak is not None:
        floors["reported_every_candidate_counts_wrong"] = bleak
    dumped = _score(
        tests,
        deliverable,
        {
            **scalars,
            rows_key: dump_rows,
        },
    )
    if dumped is not None:
        floors["reported_every_candidate"] = dumped
    return floors


def _wrong(value):
    """A value of the right type that is certainly not the right answer."""

    if isinstance(value, bool):
        return not value
    if isinstance(value, (int, float)):
        return int(value) + 9973
    return "not-the-answer"


def _deliverable_of(criteria_path: Path) -> str | None:
    return _literal_of(criteria_path, "DELIVERABLE")


def _restated_of(criteria_path: Path) -> frozenset[str]:
    value = _literal_of(criteria_path, "RESTATED_FROM_BRIEF")
    if isinstance(value, (tuple, list)):
        return frozenset(value)
    return frozenset()


def _literal_of(path: Path, name: str):
    """Read one module-level literal without importing the module.

    Importing `criteria` here would put the task's `sys.path` insert and
    its `from criteria_base import *` into this process, which is how a
    build ends up grading one task with another's constants.
    """

    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                try:
                    return ast.literal_eval(node.value)
                except ValueError:
                    return None
    return None


def render(name: str, floors: dict[str, float]) -> str:
    if not floors:
        return f"{name}: baselines could not be measured"
    parts = ", ".join(f"{label} {value:.3f}" for label, value in sorted(floors.items()))
    return f"{name}: floors — {parts}"


__all__ = ["measure", "render"]
