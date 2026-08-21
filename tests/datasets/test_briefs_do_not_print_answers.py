"""A worked example in a brief must name nothing the answer contains.

`no-op-revision-register` illustrated its output with
`"document_ref": "LEGAL!12.3"`, and `LEGAL!12.3` was one of the twenty
true rows. Row F1 keys on `document_ref` alone, so the brief handed every
reader one row of recall and its three graded fields for reading the
example — 5% of the row set, before opening a tool.

The example is worth keeping; the fix is that it must name nothing real.
An author cannot check that by eye, because the oracle is re-derived
every time the world is: a value that was safe last month is a row this
month. When this check was first run it found a *second* occurrence the
author had missed while fixing the first — the prose paragraph beneath
the skeleton, explaining the id format with the same real row.

Only row keys are checked here. Scalars are a different question with a
different answer: `window_end` appears in the brief because the brief
states the window, which is why it is graded in the diagnostic dimension
rather than the reward.
"""

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "datasets" / "merrick" / "tasks"
sys.path.insert(0, str(REPO / "datasets" / "merrick"))


def _built() -> list[str]:
    if not TASKS.is_dir():
        return []
    return sorted(
        p.name
        for p in TASKS.iterdir()
        if p.is_dir() and (p / "tests" / "oracle.json").is_file()
    )


BUILT = _built()


def test_there_are_built_tasks_to_check() -> None:
    assert BUILT, "no built tasks; this file would pass by having nothing to do"


@pytest.mark.parametrize("task", BUILT)
def test_the_brief_names_no_scoring_row(task: str) -> None:
    import build_tasks

    path = TASKS / task
    answer = json.loads((path / "tests" / "oracle.json").read_text())
    build_tasks._refuse_leaked_rows(path, answer, task)


def test_the_check_catches_a_leak(tmp_path: Path) -> None:
    """Guard the guard. Every real brief passing proves nothing unless a
    brief that leaks is refused."""

    import build_tasks

    task = tmp_path / "leaky"
    (task / "tests").mkdir(parents=True)
    (task / "instruction.md").write_text(
        'Example row: {"ref": "msg-000104", "who": "Ana"}\n'
    )
    (task / "tests" / "criteria.py").write_text(
        'DELIVERABLE = "x.json"\nROWS = "hits"\nKEY = ("ref",)\n'
    )
    answer = {"hits": [{"ref": "msg-000104", "who": "Ana"}]}
    with pytest.raises(SystemExit) as caught:
        build_tasks._refuse_leaked_rows(task, answer, "leaky")
    assert "msg-000104" in str(caught.value)


def test_a_brief_that_names_nothing_real_passes(tmp_path: Path) -> None:
    import build_tasks

    task = tmp_path / "clean"
    (task / "tests").mkdir(parents=True)
    (task / "instruction.md").write_text('Example row: {"ref": "msg-000000"}\n')
    (task / "tests" / "criteria.py").write_text(
        'DELIVERABLE = "x.json"\nROWS = "hits"\nKEY = ("ref",)\n'
    )
    build_tasks._refuse_leaked_rows(task, {"hits": [{"ref": "msg-000104"}]}, "clean")
