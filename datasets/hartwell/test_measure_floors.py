"""Integration regressions for Hartwell's shared request-audit floors."""

import subprocess
import sys
from pathlib import Path

import pytest

HARTWELL = Path(__file__).parent
TASKS = HARTWELL / "tasks"

pytestmark = pytest.mark.skipif(
    not all(
        (TASKS / task / "bundle").exists()
        for task in ("second-read-audit", "visitor-log-audit")
    ),
    reason="task bundles not built; run datasets/hartwell/build_tasks.py",
)


def test_second_read_and_visitor_floors_keep_independent_semantics() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(HARTWELL / "measure_floors.py"),
            "second-read-audit",
            "visitor-log-audit",
        ],
        cwd=HARTWELL.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == [
        "second-read-audit: floor=54 cap=162",
        "visitor-log-audit: floor=54 cap=162",
    ]
