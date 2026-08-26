"""The numbers `docs/TASK-PIPELINE.md` argues from, checked against the data.

Four audit passes over that document found four defects and not one of
them was in the code:

    flatly wrong     calder recorded as "82 owner-mails, zero deadline
                     forms -- none at all"; it is the densest world of the
                     four, with 392 admitted commitments
    scope-ambiguous  "8 of 52 titles" measured the corpus while the
                     sentence said "inside the window", where it is 8 of 17
    stale by decay   "61 carry a promise" -> 58 under fourteen corrections
    stale but honest the `I'll` counts, which name the corpus they measured
                     and are therefore harmless

The briefs, over the same period, held up exactly. The difference is not
care: every brief figure sits under a digest pin, so changing the prose
around it refuses the build and forces a re-read. The document had no such
mechanism, so it decayed quietly for weeks with three correct rows sitting
beside the wrong one.

This is that mechanism. It re-measures the load-bearing figures and asserts
the document still contains them, so a rule change that moves a number
fails here and names the line to fix.

Only figures that are genuinely derivable are pinned. A claim that names
the corpus it measured ("measured on 56 recorded days") is a historical
record, not a live one, and is deliberately left alone.
"""

import importlib.util
import sqlite3
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
DOC = REPO / "docs" / "TASK-PIPELINE.md"


def _rule():
    path = REPO / "datasets" / "merrick" / "promise_rule.py"
    spec = importlib.util.spec_from_file_location("_pipeline_doc_rule", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _mails(world: str, task: str) -> list[str]:
    state = REPO / "datasets" / world / "tasks" / task / "bundle" / "state" / "gmail.db"
    if not state.is_file():
        pytest.skip(f"{world}/{task} has no served mail")
    connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    return [row[0] or "" for row in connection.execute("SELECT body FROM messages")]


def _says(number: int) -> bool:
    """Whether the document contains the figure, spaced or plain."""

    text = DOC.read_text(encoding="utf-8")
    plain = f"{number}"
    spaced = f"{number // 1000} {number % 1000:03d}" if number >= 1000 else plain
    return plain in text or spaced in text


@pytest.mark.parametrize(
    ("world", "task"),
    [("hartwell", "client-departure-postmortem"), ("calder", "h1-billing-audit")],
)
def test_the_world_table_still_matches_the_worlds(world: str, task: str) -> None:
    """The table that ranks worlds by how many commitments they carry.

    calder's row was wrong here by more than an order of magnitude and the
    argument built on it ran backwards.
    """

    rule = _rule()
    bodies = _mails(world, task)
    assert bodies, f"{world} served no mail — the check would pass vacuously"
    admitted = sum(1 for body in bodies if rule.commitment_in(body))
    owner = sum(1 for body in bodies if rule._OWNER.search(body))
    for label, value in (
        ("mails", len(bodies)),
        ("owner-mails", owner),
        ("admitted", admitted),
    ):
        assert _says(value), (
            f"{DOC.name} no longer states {world}'s {label} = {value}. Re-measure "
            "the world table and correct the row rather than the measurement"
        )


def test_the_standing_series_figures_name_the_window_they_measure() -> None:
    """8 of 17 inside the window; 8 of 52 across the corpus. Both, labelled."""

    import datetime as dt
    from collections import defaultdict
    from zoneinfo import ZoneInfo

    state = (
        REPO
        / "datasets"
        / "merrick"
        / "tasks"
        / "live-commitment-register"
        / "environment"
        / ".workbench"
        / "state"
        / "meetings.db"
    )
    if not state.is_file():
        pytest.skip("live-commitment-register is not staged")
    connection = sqlite3.connect(f"file:{state}?mode=ro", uri=True)
    meta = dict(connection.execute("SELECT key, value FROM meta"))
    epoch = dt.datetime.fromisoformat(meta["epoch"])
    zone = ZoneInfo(meta["timezone"])

    everywhere: dict[str, set] = defaultdict(set)
    inside: dict[str, set] = defaultdict(set)
    for title, started in connection.execute("SELECT title, started FROM meetings"):
        day = (epoch + dt.timedelta(seconds=started)).astimezone(zone).date()
        everywhere[title].add(day)
        if dt.date(2026, 1, 6) <= day <= dt.date(2026, 2, 16):
            inside[title].add(day)

    standing_inside = sum(1 for days in inside.values() if len(days) >= 3)
    assert (standing_inside, len(inside)) == (8, 17), (
        f"the window now holds {standing_inside} standing series of "
        f"{len(inside)} titles, not 8 of 17 — correct the document"
    )
    standing_all = sum(1 for days in everywhere.values() if len(days) >= 3)
    assert (standing_all, len(everywhere)) == (8, 52), (
        f"the corpus now holds {standing_all} of {len(everywhere)}, not 8 of 52"
    )
    assert _says(17) and _says(52), (
        f"{DOC.name} must state BOTH scopes. Giving one while naming the other "
        "is what made this line read as an error for weeks"
    )
