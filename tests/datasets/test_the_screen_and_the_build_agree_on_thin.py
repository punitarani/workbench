"""Two constants, in two files, that must not drift apart.

`measure_commitment_window.ROW_FLOOR` is what the window screen refuses
below: a reader chooses a window with that script, and it says "usable" or
"UNDER THE ROW FLOOR".

`build_tasks.THIN_ROWS` is what the build refuses below, added on
2026-08-23 after `degenerate` had reported thin registers for months
without anything acting on the report.

Both are 12 today, and neither knows the other exists. If either moves, the
screen certifies a window the build then refuses — and the failure arrives
one step later than the decision that caused it, wearing a message about
the oracle rather than about the window. That is the shape this dataset has
paid for repeatedly: a gate consulted *instead of* looking, holding a
number that drifted.

The right repair is arguably one constant imported by both. It is not done
that way because `build_tasks` imports the whole materializer and analysis
stack, and a small measurement script that a person runs interactively
should not pay for that to learn a number. So they stay separate and this
test is the seam.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MERRICK = REPO / "datasets" / "merrick"


def _literal(path: Path, name: str) -> int:
    match = re.search(rf"^{name}\s*=\s*(\d+)\s*$", path.read_text(), re.M)
    assert match, f"{name} not found as a module-level int in {path.name}"
    return int(match.group(1))


def test_the_window_screen_and_the_build_refuse_at_the_same_size() -> None:
    screen = _literal(MERRICK / "measure_commitment_window.py", "ROW_FLOOR")
    build = _literal(MERRICK / "build_tasks.py", "THIN_ROWS")
    assert screen == build, (
        f"the window screen accepts {screen} rows and the build refuses under "
        f"{build}. A window chosen with the screen would be refused by the "
        "build, and the message would be about the oracle rather than about "
        "the window."
    )


def test_both_are_read_from_the_files_that_use_them() -> None:
    """Guard the guard.

    A regex that stops matching returns nothing to compare, and two
    absences are equal. `_literal` asserts on the match for that reason;
    this checks the values are the plausible size of a register rather than
    whatever a loosened pattern first finds.
    """

    for path, name in (
        (MERRICK / "measure_commitment_window.py", "ROW_FLOOR"),
        (MERRICK / "build_tasks.py", "THIN_ROWS"),
    ):
        value = _literal(path, name)
        assert 2 <= value <= 100, f"{name} = {value}, which is not a register size"
