"""Safe Reward Kit criteria for the Calder H1 billing audit."""

import json
from pathlib import Path

from rewardkit import criterion

MAX_DELIVERABLE_BYTES = 200_000
TOP_FIELDS = frozenset(
    {
        "total_logged_hours",
        "matters_by_hours",
        "worked_but_untimed",
        "untouched_matters",
        "cam_dispute",
    }
)
CAM_FIELDS = frozenset(
    {
        "admin_overhead_usd",
        "utilities_usd",
        "credit_usd",
        "net_reduction_usd",
        "final_position_date",
        "final_position_message_id",
    }
)
HOURS_TOLERANCE = 0.05


def _submitted(workspace: Path, path: str) -> dict | None:
    deliverable = workspace / path
    if not deliverable.is_file():
        return None
    if deliverable.stat().st_size > MAX_DELIVERABLE_BYTES:
        return None
    try:
        got = json.loads(deliverable.read_text(encoding="utf-8"))
    except ValueError, UnicodeDecodeError:
        return None
    return got if isinstance(got, dict) else None


def _close(got: object, expected: float) -> bool:
    return isinstance(got, (int, float)) and abs(float(got) - expected) <= (
        HOURS_TOLERANCE
    )


def _ledger_ok(got: object, expected: list[dict]) -> bool:
    if not isinstance(got, list) or len(got) != len(expected):
        return False
    want = {row["ticket_id"]: row["hours"] for row in expected}
    seen: dict[str, float] = {}
    previous = float("inf")
    for row in got:
        if not isinstance(row, dict) or set(row) != {"ticket_id", "hours"}:
            return False
        ticket, hours = row["ticket_id"], row["hours"]
        if ticket not in want or ticket in seen:
            return False
        if not _close(hours, want[ticket]):
            return False
        if float(hours) > previous + HOURS_TOLERANCE:
            return False
        previous = float(hours)
        seen[ticket] = float(hours)
    return set(seen) == set(want)


@criterion(
    shared=True, description="deliverable parses with exactly the required fields"
)
def schema_ok(workspace: Path, path: str) -> bool:
    got = _submitted(workspace, path)
    return (
        got is not None
        and set(got) == TOP_FIELDS
        and isinstance(got.get("cam_dispute"), dict)
        and set(got["cam_dispute"]) == CAM_FIELDS
    )


@criterion(shared=True, description="firm-wide logged hours match")
def total_hours(workspace: Path, path: str, expected: float) -> bool:
    got = _submitted(workspace, path)
    return got is not None and _close(got.get("total_logged_hours"), expected)


@criterion(shared=True, description="per-matter hours ledger matches")
def ledger(workspace: Path, path: str, expected: list) -> bool:
    got = _submitted(workspace, path)
    return got is not None and _ledger_ok(got.get("matters_by_hours"), expected)


@criterion(shared=True, description="hygiene findings match")
def hygiene(workspace: Path, path: str, worked: list, untouched: list) -> bool:
    got = _submitted(workspace, path)
    return (
        got is not None
        and got.get("worked_but_untimed") == worked
        and got.get("untouched_matters") == untouched
    )


@criterion(shared=True, description="CAM dispute final position matches")
def cam_dispute(workspace: Path, path: str, expected: dict) -> bool:
    got = _submitted(workspace, path)
    if got is None or not isinstance(got.get("cam_dispute"), dict):
        return False
    cam = got["cam_dispute"]
    return all(cam.get(key) == expected[key] for key in CAM_FIELDS)


@criterion(shared=True, description="the full audit is certified correct")
def certified(workspace: Path, path: str, truth: dict) -> bool:
    got = _submitted(workspace, path)
    if got is None or set(got) != TOP_FIELDS:
        return False
    cam = got.get("cam_dispute")
    return (
        _close(got.get("total_logged_hours"), truth["total_logged_hours"])
        and _ledger_ok(got.get("matters_by_hours"), truth["matters_by_hours"])
        and got.get("worked_but_untimed") == truth["worked_but_untimed"]
        and got.get("untouched_matters") == truth["untouched_matters"]
        and isinstance(cam, dict)
        and set(cam) == CAM_FIELDS
        and all(cam.get(key) == truth["cam_dispute"][key] for key in CAM_FIELDS)
    )
