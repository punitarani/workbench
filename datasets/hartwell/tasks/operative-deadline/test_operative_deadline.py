"""Task-level verification: solve.sh earns full reward, the last-notice
assumption baseline earns strictly less, and the grader is deterministic.

Needs the built environment bundle (data, local-only):
    uv run python datasets/hartwell/build_tasks.py
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"

pytestmark = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def run_grader(tmp_path: Path, produce: Path) -> dict:
    """Reproduce the split the harness runs: the tool databases sit in
    ``state/``, a sibling of the agent's workspace, and both the solution
    and the grader work from ``workspace/``."""
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    subprocess.run(
        ["bash", str(produce)], cwd=workspace, check=True, capture_output=True
    )
    logs = tmp_path / "logs"
    result = subprocess.run(
        [sys.executable, str(TASK / "tests" / "grade.py")],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
        env={
            "VERIFIER_LOG_DIR": str(logs),
            "WORKBENCH_STATE": str(bundle / "state"),
            "PATH": "/usr/bin:/bin",
        },
    )
    reward = json.loads((logs / "reward.json").read_text())
    assert result.stdout.strip(), "grader prints its verdict"
    return reward


def test_solution_earns_full_reward(tmp_path: Path) -> None:
    reward = run_grader(tmp_path, TASK / "solution" / "solve.sh")
    assert reward["score"] == pytest.approx(1.0), reward


def test_naive_baseline_earns_strictly_less(tmp_path: Path) -> None:
    solved = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive = run_grader(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["score"] < solved["score"] - 0.4, (
        f"the Slack correction must discriminate: naive={naive['score']}"
    )
    assert naive["score"] > 0.1, "the notice history still earns the baseline credit"


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    empty = tmp_path / "noop.sh"
    empty.write_text("true\n")
    reward = run_grader(tmp_path, empty)
    assert reward["score"] == 0.0


def test_grading_is_deterministic(tmp_path: Path) -> None:
    first = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    second = run_grader(tmp_path / "b", TASK / "solution" / "solve.sh")
    assert first == second
