"""Everything shipped in a task's `tests/` must survive being imported.

The grader imports *every* `.py` under the tests directory before it
computes anything. One that raises on import takes the whole discovery
down: no criteria register, no reward file is written, and the trial ends
as an **error** rather than a score.

That is what happened. Merrick kept each task's independent second
derivation at `tests/verify.py`, and its first statement is

    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

which resolves to the dataset root in the repo and raises `IndexError`
in the container, where the directory is mounted at `/tests` and has two
parents. Every trial of every Merrick task would have errored. Ashgrove
never had the problem because its second derivation lives at the dataset
root, outside the directory that ships — so the two datasets disagreed
about what `tests/` is for, and only one of them was right.

Two checks, and **neither one is sufficient**, which is worth stating
because the obvious reading is that the first one covers it.

Running the real entry point — `test.sh` over an empty workspace — is the
better test in principle: an empty workspace is a legitimate answer, a
working grader scores it zero, and a crashing one writes no reward at
all. But it runs on the host, where the repository really is three levels
up, so `parents[3]` resolves and the defect does not reproduce. Confirmed
by putting the file back: the entry-point test stayed green.

So the static check is what actually covers the container, by naming the
property directly — a file shipped to `/tests` must not index above its
own directory. It is the weaker kind of test and it is the one that
catches this.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DATASETS = REPO / "datasets"


def _built_tasks() -> list[Path]:
    found = []
    for dataset in sorted(DATASETS.iterdir()):
        tasks = dataset / "tasks"
        if not tasks.is_dir():
            continue
        found += [
            task
            for task in sorted(tasks.iterdir())
            if (task / "tests" / "test.sh").is_file()
            and (task / "tests" / "oracle.json").is_file()
        ]
    return found


def _task_id(task: Path) -> str:
    return f"{task.parent.parent.name}/{task.name}"


BUILT = _built_tasks()
HAS_REWARDKIT = shutil.which("rewardkit") is not None


@pytest.mark.skipif(not BUILT, reason="no built tasks to check")
def test_there_are_built_tasks() -> None:
    assert BUILT


@pytest.mark.skipif(not HAS_REWARDKIT, reason="rewardkit is not on PATH")
@pytest.mark.parametrize("task", BUILT, ids=_task_id)
def test_the_grader_scores_an_empty_workspace(task: Path, tmp_path: Path) -> None:
    """An empty workspace is a legitimate answer — a trial that wrote
    nothing. It must score, not crash."""

    workspace = tmp_path / "workspace"
    logs = tmp_path / "logs"
    workspace.mkdir()
    logs.mkdir()
    result = subprocess.run(
        ["sh", str(task / "tests" / "test.sh")],
        cwd=task,
        env={
            **os.environ,
            "WORKBENCH_WORKSPACE": str(workspace),
            "VERIFIER_LOG_DIR": str(logs),
        },
        capture_output=True,
        text=True,
        timeout=300,
    )
    reward = logs / "reward.json"
    assert reward.is_file(), (
        f"{task.name}: the grader produced no reward file. A trial gets an "
        f"error rather than a score.\n"
        f"exit {result.returncode}\n{result.stdout[-1500:]}\n{result.stderr[-1500:]}"
    )
    scored = json.loads(reward.read_text())
    assert set(scored) >= {"reward", "answer", "process"}, scored


@pytest.mark.parametrize("task", BUILT, ids=_task_id)
def test_nothing_shipped_reaches_above_its_own_directory(task: Path) -> None:
    """The static half, so the reason is legible when the entry-point test
    fails. A grading file that indexes `parents[2]` or beyond is assuming
    a repository above it, and in the container there is none."""

    import re

    reaching = re.compile(r"parents\[(\d+)\]")
    offenders = []
    for source in sorted((task / "tests").rglob("*.py")):
        for depth in reaching.findall(source.read_text(encoding="utf-8")):
            if int(depth) >= 2:
                offenders.append(f"{source.relative_to(task)}: parents[{depth}]")
    assert not offenders, (
        f"{task.name}: {offenders}. In the container this directory is "
        "mounted at /tests and has two parents; indexing past that raises "
        "on import and takes the whole grader down with it."
    )
