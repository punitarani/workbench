"""Integration regressions for Hartwell's shared request-audit floors."""

import runpy
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

HARTWELL = Path(__file__).parent
TASKS = HARTWELL / "tasks"

pytestmark = pytest.mark.skipif(
    not all(
        (TASKS / task / "bundle").exists()
        for task in ("second-read-audit", "visitor-log-audit")
    ),
    reason="task bundles not built; run datasets/hartwell/build_tasks.py",
)


def test_second_read_and_visitor_floors_keep_independent_semantics() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(HARTWELL / "measure_floors.py"),
            "second-read-audit",
            "visitor-log-audit",
        ],
        cwd=HARTWELL.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.splitlines() == [
        "second-read-audit: floor=54",
        "visitor-log-audit: floor=54",
    ]


def test_measure_api_returns_only_the_observed_floor() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]

    assert "tuple[int, int]" not in str(measure.__annotations__.get("return"))


def test_fee_floor_discovers_meridian_through_current_clio_fields() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(HARTWELL / "measure_floors.py"),
            "fee-dispute-reconstruction",
        ],
        cwd=HARTWELL.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "fee-dispute-reconstruction: floor=49"


def test_fee_floor_metadata_matches_the_measured_reference_path() -> None:
    manifest = tomllib.loads(
        (TASKS / "fee-dispute-reconstruction" / "task.toml").read_text()
    )

    assert manifest["metadata"]["reference_tool_path_calls"] == 49


def test_visitor_custody_uses_the_first_qualifying_return() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    outcome = namespace["_custody_outcome"]
    assert callable(outcome)

    epoch = date(2026, 3, 2)
    friday = date(2026, 4, 17)
    asked_at = (friday - epoch).days * 86_400 + 12 * 3_600
    sunday = asked_at + 2 * 86_400
    monday = asked_at + 3 * 86_400

    assert outcome(friday, asked_at, [sunday, monday]) == (False, False, False)
    assert outcome(friday, asked_at, [monday]) == (False, True, True)
    assert outcome(friday, asked_at, [asked_at - 60, monday]) == (
        False,
        True,
        True,
    )
