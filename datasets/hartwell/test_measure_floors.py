"""Integration regressions for Hartwell's shared request-audit floors."""

import asyncio
import json
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


def test_billing_floor_certifies_the_complete_daily_review() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "billing-hygiene-audit" / "tests" / "oracle.json").read_text()
    )
    assert asyncio.run(measure("billing-hygiene-audit")) == 146
    oracle["daily_review"][0]["sent_slack_ts"][0] = "invented-message"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("billing-hygiene-audit"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)


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


def test_fee_floor_certifies_the_complete_support_workpaper() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "fee-dispute-reconstruction" / "tests" / "oracle.json").read_text()
    )
    oracle["support_audit"][1]["slack_message_ts"][0] = "invented-message"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("fee-dispute-reconstruction"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)


def test_vanished_floor_certifies_the_full_revision_ledger() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "vanished-clause" / "tests" / "oracle.json").read_text()
    )
    oracle["revision_audit"][0]["coverage_status"] = "unreviewed"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("vanished-clause"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)


def test_vanished_floor_metadata_matches_the_measured_reference_path() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(HARTWELL / "measure_floors.py"),
            "vanished-clause",
        ],
        cwd=HARTWELL.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = tomllib.loads((TASKS / "vanished-clause" / "task.toml").read_text())

    assert completed.stdout.strip() == "vanished-clause: floor=199"
    assert manifest["metadata"]["reference_tool_path_calls"] == 199


def test_standard_floor_certifies_the_full_version_audit() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "standard-drift" / "tests" / "oracle.json").read_text()
    )
    oracle["version_audit"][0]["change_class"] = "substantive"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("standard-drift"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)


def test_standard_floor_metadata_matches_the_measured_reference_path() -> None:
    completed = subprocess.run(
        [sys.executable, str(HARTWELL / "measure_floors.py"), "standard-drift"],
        cwd=HARTWELL.parents[1],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = tomllib.loads((TASKS / "standard-drift" / "task.toml").read_text())

    assert completed.stdout.strip() == "standard-drift: floor=48"
    assert manifest["metadata"]["reference_tool_path_calls"] == 48


def test_second_read_floor_certifies_the_full_first_response_audit() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "second-read-audit" / "tests" / "oracle.json").read_text()
    )
    assert asyncio.run(measure("second-read-audit")) == 54
    oracle["response_audit"][0]["first_response_id"] = "invented-response"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("second-read-audit"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)


def test_visitor_custody_uses_the_first_qualifying_return() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    outcome = namespace["_custody_outcome"]
    assert callable(outcome)

    friday = date(2026, 4, 17)
    day_seconds = namespace["_day_seconds"]
    asked_at = day_seconds(friday.isoformat()) + 12 * 3_600
    sunday = day_seconds("2026-04-19") + 12 * 3_600
    monday = day_seconds("2026-04-20") + 12 * 3_600

    assert outcome(friday, asked_at, [sunday, monday]) == (False, True, True)
    assert outcome(friday, asked_at, [monday]) == (False, True, True)
    assert outcome(friday, asked_at, [asked_at - 60, monday]) == (
        False,
        True,
        True,
    )


def test_visitor_floor_certifies_the_full_custody_audit() -> None:
    namespace = runpy.run_path(str(HARTWELL / "measure_floors.py"))
    measure = namespace["measure"]
    oracle = json.loads(
        (TASKS / "visitor-log-audit" / "tests" / "oracle.json").read_text()
    )
    assert asyncio.run(measure("visitor-log-audit")) == 54
    oracle["custody_audit"][0]["first_return_id"] = "invented-return"
    measure.__globals__["_oracle"] = lambda task: oracle

    with pytest.raises(BaseExceptionGroup) as caught:
        asyncio.run(measure("visitor-log-audit"))
    pending = list(caught.value.exceptions)
    leaves: list[BaseException] = []
    while pending:
        exception = pending.pop()
        if isinstance(exception, BaseExceptionGroup):
            pending.extend(exception.exceptions)
        else:
            leaves.append(exception)
    assert any(isinstance(exception, AssertionError) for exception in leaves)
