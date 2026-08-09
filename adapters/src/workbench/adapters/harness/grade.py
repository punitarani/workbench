"""Run a task's own grader against an episode workspace.

The harness never reimplements reward logic: it executes the task's
``tests/grade.py`` with the workspace as cwd (the in-container verifier
contract) and reads back the reward JSON it writes to
``$VERIFIER_LOG_DIR``.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


class GraderError(RuntimeError):
    """The task grader failed, or produced no reward.json."""


def grade_episode(task_dir: Path, workspace_dir: Path) -> dict:
    # Resolve before the cwd switch below: task_dir is often repo-relative.
    grader = (task_dir / "tests" / "grade.py").resolve()
    if not grader.is_file():
        raise GraderError(f"no grader at {grader}")
    with tempfile.TemporaryDirectory(prefix="verifier-") as log_dir:
        completed = subprocess.run(
            [sys.executable, str(grader)],
            cwd=workspace_dir,
            capture_output=True,
            text=True,
            env={**os.environ, "VERIFIER_LOG_DIR": log_dir},
        )
        if completed.returncode != 0:
            raise GraderError(
                f"grader exited {completed.returncode}: {completed.stderr[:500]}"
            )
        reward_path = Path(log_dir) / "reward.json"
        if not reward_path.is_file():
            raise GraderError(f"grader wrote no reward.json: {completed.stdout[:500]}")
        return json.loads(reward_path.read_text(encoding="utf-8"))
