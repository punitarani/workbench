"""A task that reports summed hours must say which way it rounds.

Adding durations and rounding the total is not the same as rounding each
duration and adding. On this record the two orders disagree for 34% of
person-and-engagement pairs, 79% of engagements, 88% of people, and every
firm-wide total — `10.78` and `10.79` are the same work counted two ways.

That is a coin toss the agent cannot win by working harder, so an
instruction that does not name the order is grading luck. It has already
happened twice:

* `engagement-time-allocation` totalled the firm's hours by adding
  already-rounded rows. 817.27 that way, 817.23 from the entries. An
  agent with all 197 rows correct lost both totals.
* `tracker-reconciliation` had the same gap and nobody had looked. It
  surfaced as 46 of 139 rows "wrong" by exactly 0.01 in a live rollout,
  every one of them the agent's sum-of-rounded against the oracle's
  round-once, and it would have been certified as a model failure.

The first fix covered that one task's *totals* and left its 188 row
figures — a third of them exposed — uncovered, which is why this is a
gate over the whole suite rather than another edit.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "datasets" / "ashgrove" / "tasks"

# The solvers all accumulate raw seconds (or minutes, or cents) and round
# as they write. Any task whose solver does that arithmetic owes its
# reader the same sentence.
_DERIVES = re.compile(r"quantity_seconds|/\s*3600|_seconds|/\s*60,\s*2")
# Said in the instruction's own words, not by keyword: "round once, at the
# end", "from the entries", "not by adding up ... already been cut".
_STATES = re.compile(
    r"round(?:ed)? once|from the (?:time )?entries themselves"
    r"|already been cut|unrounded",
    re.IGNORECASE,
)


def _hours_tasks() -> list[Path]:
    found = []
    for task in sorted(p for p in TASKS.iterdir() if p.is_dir()):
        solver = task / "solution" / "solve.py"
        if solver.is_file() and _DERIVES.search(solver.read_text()):
            found.append(task)
    return found


HOURS_TASKS = _hours_tasks()


def test_the_audit_found_tasks_to_check() -> None:
    """Guard the guard: a regex that matches nothing passes vacuously."""

    assert len(HOURS_TASKS) >= 5, [p.name for p in HOURS_TASKS]


@pytest.mark.parametrize("task", HOURS_TASKS, ids=lambda p: p.name)
def test_it_says_which_way_it_rounds(task: Path) -> None:
    instruction = (task / "instruction.md").read_text()
    assert _STATES.search(instruction), (
        f"{task.name} derives figures from raw durations but its instruction "
        "never says whether to round once at the end or to add up rounded "
        "values. The two disagree on a third of this world's rows, so the "
        "criterion grades which convention the agent happened to pick."
    )
