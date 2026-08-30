"""`docs/PACK.md`'s world table must match the worlds it describes.

Every number in that table drifted at least once. The day count carried two
different definitions in one column -- one world's configured window end
against the other's span of recorded meetings -- and the assignment counts
beside it were measured before the rule they count was tightened, so they
were high by an eighth.

Those are the numbers a reader checks first, and they are the cheapest in
the pack to derive, which is the whole argument for deriving them.

`days` is defined here as the span from the first recorded meeting to the
last, inclusive, because that is a fact about the corpus. A configured
window end is a fact about a task.

Skips rather than fails when a world is not materialised: `out/` is not
distributed, and a clone that cannot see the worlds should not be told its
documentation is wrong.
"""

import datetime as dt
import re
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PACK = REPO / "docs" / "PACK.md"


def _row(world: str) -> list[str] | None:
    for line in PACK.read_text().splitlines():
        if line.startswith(f"| `{world}`"):
            return [cell.strip() for cell in line.strip("|").split("|")]
    return None


@pytest.mark.parametrize("world", ["merrick", "delegation"])
def test_the_table_is_the_world(world: str) -> None:
    state = REPO / "out" / world / "bundle" / "state"
    if not (state / "meetings.db").is_file():
        pytest.skip(f"{world} is not materialised here")
    row = _row(world)
    assert row is not None, f"PACK.md has no row for {world}"

    meetings = sqlite3.connect(f"file:{state / 'meetings.db'}?mode=ro", uri=True)
    started = [s for (s,) in meetings.execute("SELECT started FROM meetings")]
    turns = [t for (t,) in meetings.execute("SELECT text FROM utterances")]
    meetings.close()
    clio = sqlite3.connect(f"file:{state / 'clio.db'}?mode=ro", uri=True)
    people = clio.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    clio.close()

    measured = {
        "days": (max(started) - min(started)) // 86_400 + 1,
        "meetings": len(started),
        "turns": len(turns),
        "words": sum(len((t or "").split()) for t in turns),
        "people": people,
    }
    stated = {
        name: int(re.sub(r"[^\d]", "", cell))
        for name, cell in zip(("days", "meetings", "turns", "words", "people"), row[1:6])
    }
    # Words are rounded in the table on purpose -- an exact figure invites a
    # reader to recount a number that moves with tokenisation. Anything
    # else is exact.
    wrong = {
        name: (stated[name], measured[name])
        for name in stated
        if (
            abs(stated[name] - measured[name]) > 500
            if name == "words"
            else stated[name] != measured[name]
        )
    }
    assert not wrong, (
        f"PACK.md's {world} row disagrees with the world: "
        + ", ".join(f"{k} says {s} and is {m}" for k, (s, m) in wrong.items())
        + ". These are the numbers a reader checks first and the cheapest "
        "in the pack to derive."
    )
