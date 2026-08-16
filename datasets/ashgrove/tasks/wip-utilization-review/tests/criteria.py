"""Grading for the WIP review: totals, per-engagement, per-person."""

import json
from pathlib import Path

from rewardkit import criterion

MAX_BYTES = 200_000
TOP = frozenset(
    {
        "client_engagements",
        "internal_engagements",
        "total_client_wip_dollars",
        "blended_rate_dollars_per_hour",
        "engagements",
        "people",
    }
)


def _submitted(workspace: Path, path: str) -> dict | None:
    deliverable = workspace / path
    if not deliverable.is_file() or deliverable.stat().st_size > MAX_BYTES:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


def _close(a, b, tol) -> bool:
    return isinstance(a, (int, float)) and abs(float(a) - float(b)) <= tol


@criterion(shared=True, description="deliverable parses with the required fields")
def schema_ok(workspace: Path, path: str) -> bool:
    got = _submitted(workspace, path)
    return got is not None and set(got) == TOP


@criterion(shared=True, description="{field} matches")
def scalar(workspace: Path, path: str, field: str, expected: float, tol: float) -> bool:
    got = _submitted(workspace, path)
    return got is not None and _close(got.get(field), expected, tol)


@criterion(shared=True, description="per-engagement figures")
def engagement_rows(workspace: Path, path: str, expected: list) -> float:
    got = _submitted(workspace, path)
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
            matched += _close(got_row.get(field), row[field], tol)
    # An engagement invented or an internal one included is a real error.
    extra = len(set(mine) - {r["engagement"] for r in expected})
    return max(0.0, (matched - 3 * extra) / checked) if checked else 0.0


@criterion(shared=True, description="per-person figures")
def person_rows(workspace: Path, path: str, expected: list) -> float:
    got = _submitted(workspace, path)
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
            matched += _close(got_row.get(field), row[field], tol)
    return matched / checked if checked else 0.0


@criterion(shared=True, description="rows are sorted as asked")
def ordered(workspace: Path, path: str) -> bool:
    got = _submitted(workspace, path)
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
