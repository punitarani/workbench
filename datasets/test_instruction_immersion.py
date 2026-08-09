"""Every task brief must read as work, not as an evaluation.

A task instruction is the only prose the agent is given, so it is the one
place the scaffolding can leak: name a config file, a database, a grader,
or the epoch arithmetic and the agent stops being a professional doing a
job. The brief may name the firm's products (Gmail, Slack, iManage, Clio)
because a professional simply has those; it may never name the machinery
that serves them.
"""

from pathlib import Path

import pytest

DATASETS = Path(__file__).parent

BANNED = (
    "mcp",
    "sqlite",
    "state/",
    ".db",
    "epoch",
    "day 0",
    "86400",
    "grader",
    "ground truth",
    "reward",
    "eval",
)

INSTRUCTIONS = sorted(DATASETS.glob("*/tasks/*/instruction.md"))


def test_every_task_ships_an_instruction() -> None:
    tasks = sorted(
        path.parent for path in DATASETS.glob("*/tasks/*/task.toml") if path.is_file()
    )
    assert tasks, "no tasks found under datasets/"
    missing = [task.name for task in tasks if not (task / "instruction.md").is_file()]
    assert not missing, f"tasks with no instruction.md: {missing}"


@pytest.mark.parametrize(
    "instruction", INSTRUCTIONS, ids=[p.parent.name for p in INSTRUCTIONS]
)
def test_instruction_names_no_scaffolding(instruction: Path) -> None:
    text = instruction.read_text(encoding="utf-8").lower()
    found = sorted(term for term in BANNED if term in text)
    assert not found, (
        f"{instruction.relative_to(DATASETS)} leaks evaluation scaffolding: {found}"
    )
