"""Grading for the WIP review: totals, per-engagement, per-person."""

import sys
from pathlib import Path

from rewardkit import criterion

_HERE = Path(__file__).resolve().parent
# `criteria_base.py` sits at the dataset root in the tree and beside this
# file in a built bundle, where `tests/` has been lifted out and the root is
# not there at all. Both go on the path, because with only one of them the
# import dies before a single criterion runs and the whole task reads as a
# build failure rather than as a grader that never loaded.
sys.path[:0] = [str(_HERE), str(_HERE.parents[2])]

from criteria_base import close, oracle, submitted  # noqa: E402

# This report is a page of counts, not a register, so it caps lower than the
# row tasks do.
MAX_BYTES = 200_000
# Read off the oracle rather than restated here: a hand-kept copy fails
# correct answers the day the report changes shape, which is exactly what it
# did once -- the list still named a key the report had dropped.
TOP = frozenset(oracle(_HERE))


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    return got is not None and set(got) == TOP


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected: float, tol: float) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    return got is not None and close(got.get(field), expected, tol)


@criterion(shared=True, description="per-engagement figures")
def engagement_rows(workspace: Path, path: str, expected: list) -> float:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None or not isinstance(got.get("engagements"), list):
        return 0.0
    mine = {
        str(r.get("engagement")): r for r in got["engagements"] if isinstance(r, dict)
    }
    checked = matched = 0
    for row in expected:
        got_row = mine.get(row["engagement"], {})
        for field, tol in (
            ("billable_hours", 0.05),
            ("wip_dollars", 1.0),
            ("staff_count", 0),
        ):
            checked += 1
            matched += close(got_row.get(field), row[field], tol)
    # An engagement invented or an internal one included is a real error.
    extra = len(set(mine) - {r["engagement"] for r in expected})
    return max(0.0, (matched - 3 * extra) / checked) if checked else 0.0


@criterion(shared=True, description="per-person figures")
def person_rows(workspace: Path, path: str, expected: list) -> float:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None or not isinstance(got.get("people"), list):
        return 0.0
    mine = {
        str(r.get("name", "")).strip().casefold(): r
        for r in got["people"]
        if isinstance(r, dict)
    }
    checked = matched = 0
    for row in expected:
        got_row = mine.get(row["name"].strip().casefold(), {})
        for field, tol in (
            ("logged_hours", 0.05),
            ("billable_hours", 0.05),
            ("utilization_pct", 0.2),
        ):
            checked += 1
            matched += close(got_row.get(field), row[field], tol)
    return matched / checked if checked else 0.0


@criterion(shared=True, description="rows are sorted as asked")
def ordered(workspace: Path, path: str) -> bool:
    got = submitted(workspace, path, MAX_BYTES)
    if got is None:
        return False
    tickets = [
        str(r.get("engagement"))
        for r in got.get("engagements", [])
        if isinstance(r, dict)
    ]
    names = [
        str(r.get("name", "")) for r in got.get("people", []) if isinstance(r, dict)
    ]
    return tickets == sorted(tickets) and names == sorted(names)
