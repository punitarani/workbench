"""A materialized workspace in the index is a dead world read as a live one.

Every dataset here builds its tasks from a world log: `build_tasks.py`
materializes the whole file room into `<task>/bundle/` and stages the
agent-visible half into `<task>/environment/`. Both are outputs. Both are
rebuilt wholesale on the next build, from whatever world log the bundle's
`SOURCE` names.

Committing them is not merely untidy. One merrick task's `environment/`
held **451 files** in the index -- a *partial* materialization of `epoch-v6`,
29% of the 1,558 files the same directory holds on disk, from a recording
that will not ship. Nothing distinguished them from a current workspace:
opening the directory showed plausible memos and workbooks at plausible
paths, and the only way to learn they were stale was to rebuild and diff.
That is the same failure as a drifted constant in a gate -- an artifact is
consulted *instead of* being derived, and it answers confidently.

Calder and Hartwell each ignore both directories per task, so the
convention existed and was two-thirds followed; merrick's task directories
simply had no `.gitignore` at all, and the 451 files went in as collateral
inside the commit that was undoing an *earlier* accidental commit of probe
values.

This test is about the index rather than the ignore files, because the
ignore file is the mechanism and the tracked state is the thing that
matters: a task could carry a perfect `.gitignore` and still have files
committed before it was added, which is exactly the state this repository
was in.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# Derived by construction: `build_tasks.py` deletes and recreates both on
# every run. `tests/` is not here -- oracle.json and oracle.world are the
# committed answer key and its provenance, and they ship.
DERIVED = ("bundle", "environment")


def _tracked(pattern: str) -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--", pattern],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _datasets() -> list[str]:
    return sorted(
        path.name for path in (REPO / "datasets").iterdir() if (path / "tasks").is_dir()
    )


@pytest.mark.parametrize("directory", DERIVED)
def test_no_task_commits_a_derived_directory(directory: str) -> None:
    tracked = _tracked(f"datasets/*/tasks/*/{directory}/*")
    assert not tracked, (
        f"{len(tracked)} derived file(s) are tracked under */{directory}/, "
        f"beginning with {tracked[:3]}. They are rebuilt from the world log "
        "on every build, so what is committed is whichever world happened to "
        "be on disk that day -- and it reads as the current one."
    )


def test_every_dataset_with_tasks_ignores_them() -> None:
    """The mechanism, one level below the assertion above.

    Without this, the first check passes for a dataset that has simply not
    been built yet, and goes red the day someone builds it -- reporting the
    build as the fault rather than the missing ignore rule.
    """

    missing: list[str] = []
    for dataset in _datasets():
        for task in sorted((REPO / "datasets" / dataset / "tasks").iterdir()):
            if not task.is_dir():
                continue
            rules = (
                (task / ".gitignore").read_text().splitlines()
                if (task / ".gitignore").is_file()
                else []
            )
            for directory in DERIVED:
                if f"{directory}/" not in rules:
                    missing.append(f"{dataset}/{task.name}: {directory}/")
    assert not missing, (
        f"task directories that do not ignore their own build output: {missing}"
    )


def test_the_answer_key_is_still_committed() -> None:
    """Guard the guard, in the direction that matters.

    An over-broad ignore rule -- `datasets/*/tasks/*/tests/` reaching one
    level too far, or a bare `*.json` -- would take the oracles with it,
    and the two tests above would go green because green is what they check
    for. A dataset with no committed answer key grades nothing.
    """

    oracles = _tracked("datasets/*/tasks/*/tests/oracle.json")
    assert len(oracles) >= 10, oracles
