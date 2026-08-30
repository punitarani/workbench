"""A graded scalar must not appear as a generated literal in the brief.

`merrick/commitment-revision-register` scored `meetings_read` while its own
brief ended "****129**** working days and ****512**** meetings", and 512 was
the value the oracle wanted. The reader was paid for copying a number out
of the page that asked for it.

It hid because 512 is *almost* the window's meeting count. The window holds
567; 512 is the STANDING meetings in it, which is the quantity the report
asks for and not the quantity the sentence appears to describe. The
manifest's comment said "nothing here is restated by the brief" while
citing, two lines below, the earlier task that had given away 10% of its
reward exactly this way.

The tell was in the scores and nobody chased it: `meetings_read` read 1.000
for every tier on every task of that world whose brief states it. A
criterion no model ever misses is either trivial or copied, and the
difference is whether the answer is printed on the page.

The brief may still DESCRIBE the window in prose -- dates, working days,
how many meetings are in it. What it may not do is print a number that a
graded scalar is checked against.
"""

import json
import re
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[2] / "datasets"


def _live_tasks() -> list[Path]:
    tasks = []
    for world in sorted(p for p in DATASETS.iterdir() if (p / "tasks").is_dir()):
        for task in sorted((world / "tasks").iterdir()):
            if not task.is_dir() or task.name.startswith("_"):
                continue
            manifest = task / "task.toml"
            if manifest.is_file() and re.search(
                r"^retired\s*=\s*true", manifest.read_text(), re.M
            ):
                continue
            if (task / "instruction.md").is_file() and (
                task / "tests" / "oracle.json"
            ).is_file():
                tasks.append(task)
    return tasks


def _excused(criteria: Path) -> set[str]:
    """Scalars the task has declared it does not score."""

    text = criteria.read_text() if criteria.is_file() else ""
    names: set[str] = set()
    for field in ("DERIVED_FROM_ROWS", "RESTATED_FROM_BRIEF"):
        match = re.search(rf"^{field}[^=]*=\s*\(([^)]*)\)", text, re.M)
        if match:
            names.update(re.findall(r'"([^"]+)"', match.group(1)))
    return names


@pytest.mark.parametrize("task", _live_tasks(), ids=lambda p: f"{p.parent.parent.name}/{p.name}")
def test_no_graded_scalar_is_printed_in_the_brief(task: Path) -> None:
    oracle = json.loads((task / "tests" / "oracle.json").read_text())
    excused = _excused(task / "tests" / "criteria.py")
    printed = {
        literal.strip()
        for literal in re.findall(r"\*{4}([^*]+)\*{4}", (task / "instruction.md").read_text())
    }
    given_away = [
        f"{name}={value}"
        for name, value in oracle.items()
        if not isinstance(value, list)
        and name not in excused
        and str(value) in printed
    ]
    assert not given_away, (
        f"{task.parent.parent.name}/{task.name} scores {given_away} and its "
        "brief prints the value. Either stop scoring it -- name it in "
        "RESTATED_FROM_BRIEF -- or stop printing it. A criterion whose "
        "answer is on the page reads 1.000 for every tier and measures none "
        "of them."
    )
