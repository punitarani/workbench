"""An answer key must be what its own solver currently produces.

A task's oracle is written by its reference solver. Nothing re-checks that
afterwards, so an oracle goes stale the moment the rule behind it changes
and the task is not rebuilt — and a stale key is not a wrong key that
errors, it is a wrong key that grades.

That is not hypothetical. Correcting one deadline form left THREE oracles
behind, and one of them belonged to a task already CERTIFIED: its record
said opus 0.477 / glm 0.398 / kimi 0.388 against a key its own solver no
longer produced. The scores barely moved when it was rebuilt, which is the
point — nothing about the numbers would have shown it.

`build_tasks.py` catches this on the tasks it builds, refusing with SOLVER
REGRESSION. It is refused ONLY while it runs, and it refuses to run at all
while a sweep is reading the task, which is exactly when a rule tends to
get fixed. This closes that window: it asks every task, at any time, with
no build.

Skips where a world is not materialised — `out/` is not distributed.
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _tasks() -> list[tuple[str, str]]:
    found = []
    for world in sorted(p for p in (REPO / "datasets").iterdir() if (p / "tasks").is_dir()):
        for task in sorted((world / "tasks").iterdir()):
            manifest = task / "task.toml"
            if manifest.is_file() and re.search(
                r"^retired\s*=\s*true", manifest.read_text(), re.M
            ):
                continue
            if (task / "solution" / "solve.py").is_file() and (
                task / "tests" / "oracle.json"
            ).is_file():
                found.append((world.name, task.name))
    return found


@pytest.mark.parametrize("world, task", _tasks(), ids=[f"{w}/{t}" for w, t in _tasks()])
def test_the_oracle_is_what_the_solver_produces(
    world: str, task: str, tmp_path: Path
) -> None:
    state = REPO / "out" / world / "bundle" / "state"
    if not (state / "meetings.db").is_file():
        pytest.skip(f"{world} is not materialised here")

    directory = REPO / "datasets" / world / "tasks" / task
    produced = tmp_path / "answer.json"
    # A clean environment, the way the build runs it: these solvers read
    # WORKBENCH_STATE at import, and inheriting a stray one from another
    # test would grade this world against another's record.
    outcome = subprocess.run(
        [sys.executable, str(directory / "solution" / "solve.py"), str(produced)],
        capture_output=True,
        text=True,
        env={
            "WORKBENCH_STATE": str(state),
            "WORKBENCH_WORKSPACE": str(REPO / "out" / world / "bundle" / "workspace"),
            "PATH": "/usr/bin:/bin",
            "PYTHONPATH": os.environ.get("PYTHONPATH", ""),
        },
    )
    assert outcome.returncode == 0 and produced.is_file(), (
        f"{world}/{task}'s solver did not run: {outcome.stderr[-400:]}"
    )

    now = json.loads(produced.read_text())
    stored = json.loads((directory / "tests" / "oracle.json").read_text())
    if now == stored:
        return

    rows = next((k for k, v in stored.items() if isinstance(v, list)), None)
    moved = []
    if rows and rows in now:
        key = lambda r: tuple(sorted((k, str(v)) for k, v in r.items()))  # noqa: E731
        moved = [f"{len(stored[rows])} -> {len(now[rows])} rows"] if len(
            stored[rows]
        ) != len(now[rows]) else [
            f"{sum(1 for a, b in zip(stored[rows], now[rows]) if a != b)} row(s) differ"
        ]
    scalars = [
        f"{k}: {stored[k]} -> {now[k]}"
        for k in stored
        if not isinstance(stored[k], list) and k in now and stored[k] != now[k]
    ]
    raise AssertionError(
        f"{world}/{task}'s oracle is not what its solver produces "
        f"({'; '.join(moved + scalars) or 'contents differ'}). A stale answer "
        "key does not error, it grades. Rebuild the task with --refresh-truth "
        "once you know why it moved, then re-score every saved sweep."
    )
