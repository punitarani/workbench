"""A brief's worked example must not contradict the rule above it.

Every task brief shows a JSON skeleton of the register it wants. The window
those rows must fall inside is stated in prose, and while a task is staged
that prose is a `«MEASURE: ...»` placeholder — which carries its own *example*
date, to show the author what shape to write.

That example date leaks. Written by hand into the skeleton and then never
revisited, it contradicts the boundary the prose eventually states. Measured
on a dry run: three agents given such a brief all identified the skeleton as
their single largest open question, all three guessed the prose was
normative, and all three were right *by reasoning rather than by
instruction*. An agent that reads the skeleton as operative instead reports
a wrong `window_end`, a `versions_read` of 120 against 86, and twelve rows
against ten — every one of those a grading failure caused by the brief.

The rule here is narrow on purpose: a concrete `YYYY-MM-DD` inside the JSON
block, in a task whose window is still unmeasured, is the leak. A placeholder
in angle brackets is how you show the shape without asserting a date.
"""

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
TASKS = REPO / "datasets" / "merrick" / "tasks"

_ISO = re.compile(r'"(\d{4}-\d{2}-\d{2})"')
_JSON_BLOCK = re.compile(r"```json(.*?)```", re.S)


def _live_briefs() -> list[Path]:
    out = []
    for brief in sorted(TASKS.glob("*/instruction.md")):
        solver = brief.parent / "solution" / "solve.py"
        if not solver.is_file():
            continue
        # A retired task keeps its brief as a record of what was tried.
        if solver.read_text(encoding="utf-8").lstrip().startswith('"""RETIRED'):
            continue
        out.append(brief)
    return out


BRIEFS = _live_briefs()


def test_the_audit_found_briefs_to_check() -> None:
    assert BRIEFS, f"no live briefs under {TASKS}"


@pytest.mark.parametrize("brief", BRIEFS, ids=lambda p: p.parent.name)
def test_the_skeleton_states_no_date_the_window_does_not(brief: Path) -> None:
    text = brief.read_text(encoding="utf-8")
    if "«MEASURE" not in text:
        # A finished task states its boundary, so a skeleton date can be
        # checked against it rather than forbidden. That check belongs to the
        # task's own verifier, which reads both.
        return
    for block in _JSON_BLOCK.findall(text):
        dates = _ISO.findall(block)
        assert not dates, (
            f"{brief.parent.name}: the register skeleton hard-codes {dates} "
            "while the window is still a «MEASURE» placeholder. The "
            "placeholder's own example date leaks here and then contradicts "
            "whatever boundary the prose finally states — a reader who takes "
            "the skeleton as operative gets a wrong window_end, a wrong "
            "count, and rows outside the window, all from the brief. Show "
            "the shape with a placeholder like "
            '"<a date inside the window>" instead.'
        )
