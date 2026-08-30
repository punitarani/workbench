"""A verifier's calendar window must be the solver's offset window.

The two derivations state their window in different units on purpose: the
solver counts DAY OFFSETS from the epoch, the verifier names CALENDAR
DATES. A boundary wrong on one side then shows up as a disagreement
instead of being shared.

The cost of that choice is that nothing makes them match. Two delegation
tasks carried `WINDOW_LAST_DATE = "2026-07-06"` -- day 182 of the SIBLING
world's epoch -- against solvers reading to day 134, which is 2026-05-19.
They were ported by hand before there was a script for it and only the
offset form was moved.

They agreed on every build for weeks, because this world's recording stops
on 2026-05-19 and there is nothing in the extra seven weeks to disagree
about. A bound with nothing beyond it cannot fail, and it would have
started lying the moment the world was extended by one day.

So the check has to be arithmetic against the epoch rather than a
comparison of outcomes: what the offset resolves to, and what the date
says, must be the same day.
"""

import datetime as dt
import re
import sqlite3
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

DATASETS = Path(__file__).resolve().parents[2] / "datasets"


def _pairs() -> list[tuple[str, Path]]:
    found = []
    for world in sorted(p for p in DATASETS.iterdir() if (p / "tasks").is_dir()):
        for task in sorted((world / "tasks").iterdir()):
            if not task.is_dir() or task.name.startswith("_"):
                continue
            manifest = task / "task.toml"
            if manifest.is_file() and re.search(
                r"^retired\s*=\s*true", manifest.read_text(), re.M
            ):
                continue
            solver, checker = task / "solution" / "solve.py", task / "checks" / "verify.py"
            state = task / "environment" / ".workbench" / "state" / "meetings.db"
            if not (solver.is_file() and checker.is_file() and state.is_file()):
                continue
            body = checker.read_text()
            if 'WINDOW_LAST_DATE = "' not in body:
                continue  # states its window in offsets only; nothing to cross-check
            found.append((f"{world.name}/{task.name}", task))
    return found


@pytest.mark.parametrize("name, task", _pairs(), ids=[n for n, _t in _pairs()])
def test_the_date_and_the_offset_are_the_same_day(name: str, task: Path) -> None:
    solver = (task / "solution" / "solve.py").read_text()
    checker = (task / "checks" / "verify.py").read_text()
    offset = re.search(r"^\s*WINDOW_LAST_DAY\s*=\s*(\d+)", solver, re.M)
    if offset is None:
        pytest.skip("the solver states a duration rather than a last day")
    stated = re.search(r'^WINDOW_LAST_DATE\s*=\s*"(\d{4}-\d{2}-\d{2})"', checker, re.M)

    state = task / "environment" / ".workbench" / "state" / "meetings.db"
    connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    connection.close()
    epoch = dt.datetime.fromisoformat(meta["epoch"])
    zone = ZoneInfo(meta.get("timezone", "America/New_York"))
    resolved = (
        epoch + dt.timedelta(seconds=int(offset.group(1)) * 86_400)
    ).astimezone(zone).date().isoformat()

    assert stated.group(1) == resolved, (
        f"{name}: the solver reads to day {offset.group(1)}, which is "
        f"{resolved}, and the verifier bounds {stated.group(1)}. The two "
        "derivations are reading different windows. They can still agree -- "
        "if the world has nothing in the gap -- which is exactly why this "
        "has to be checked by arithmetic and not by whether they agreed."
    )
