"""Synthetic contract tests for the operative-deadline verifier."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

TASK = Path(__file__).parent
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
T = json.loads((TESTS / "ground_truth.json").read_text())
ORACLE = json.loads((TESTS / "oracle.json").read_text())
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return {
        "operative_date": T["operative_date"],
        "operative_time": "09:00",
        "correction_ts": T["correction_ts_prefix"] + ".002908",
        "superseded_dates": deepcopy(T["superseded_dates"]),
        "supersessions": [
            {
                "invalidated": record["invalidated"],
                "by": record["by_prefix"]
                + (".002908" if record["by_prefix"].isdigit() else ""),
            }
            for record in T["supersessions"]
        ],
        "stale_calendar_refs": [
            record["id"] if record["kind"] == "email" else record["ts_prefix"] + ".001"
            for record in T["stale_calendar_refs"]
        ],
        "notice_audit": deepcopy(ORACLE["notice_audit"]),
    }


def _grade(
    tmp_path: Path, answer: object | None, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "deadline.json").write_text(raw)
    elif answer is not None:
        (workspace / "deadline.json").write_text(json.dumps(answer, allow_nan=True))
    output = tmp_path / "reward.json"
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.read_text())


def test_exact_answer_has_canonical_dimensions(tmp_path: Path) -> None:
    assert _grade(tmp_path, _perfect()) == {"answer": 1.0, "process": 0.0}


@pytest.mark.parametrize("field", ["supersessions", "stale_calendar_refs"])
def test_sets_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path, field: str
) -> None:
    near = _perfect()
    near[field].pop()
    shotgun = _perfect()
    shotgun[field].extend(deepcopy(shotgun[field][:1]) * 20)
    duplicate = _perfect()
    duplicate[field].append(deepcopy(duplicate[field][0]))
    reordered = _perfect()
    reordered[field].reverse()
    near_score = _grade(tmp_path / "near", near)["answer"]
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score < 1.0
    assert 0.0 < _grade(tmp_path / "dup", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "order", reordered)["answer"] == 1.0


def test_superseded_dates_remain_ordered_and_position_aware(tmp_path: Path) -> None:
    answer = _perfect()
    answer["superseded_dates"].reverse()
    assert 0.92 < _grade(tmp_path, answer)["answer"] < 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "numeric_ts",
        "numeric_stale",
        "bool_date",
        "nested_extra",
        "nonfinite",
    ],
)
def test_type_invalid_contract_scores_zero(tmp_path: Path, mutation: str) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["evidence"] = []
    elif mutation == "missing":
        answer.pop("operative_date")
    elif mutation == "numeric_ts":
        answer["correction_ts"] = 8767500
    elif mutation == "numeric_stale":
        answer["stale_calendar_refs"][0] = 289
    elif mutation == "bool_date":
        answer["superseded_dates"][0] = True
    elif mutation == "nested_extra":
        answer["supersessions"][0]["kind"] = "email"
    else:
        answer["superseded_dates"][0] = float("nan")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "bad", None, "{")["answer"] == 0.0
    assert _grade(tmp_path / "large", None, "x" * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "truth.json"
    (workspace / "deadline.json").symlink_to(target)
    target.parent.mkdir()
    target.write_text(json.dumps(_perfect()))
    output = tmp_path / "link" / "reward.json"
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(output.read_text())["answer"] == 0.0


@pytest.mark.parametrize(
    "call,expected",
    [
        ({"function_name": "slack__slack_search_public_and_private"}, 1.0),
        (
            {
                "function_name": "exec",
                "arguments": {
                    "input": "await tools.slack__slack_search_public_and_private({})"
                },
            },
            1.0,
        ),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "slack_search_public_and_private would help"},
            },
            0.0,
        ),
    ],
)
def test_process_detects_native_and_unified_calls_not_mentions(
    tmp_path: Path, call: dict[str, object], expected: float
) -> None:
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(json.dumps({"steps": [{"tool_calls": [call]}]}))
    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TESTS / "criteria.py", tests / "criteria.py")
    (tests / "process" / "method.py").write_text(
        "import rewardkit as rk\n"
        f"rk.tool_invoked('slack_search_public_and_private', "
        f"path={str(trajectory)!r}, name='used')\n"
    )
    output = tmp_path / "process.json"
    subprocess.run(
        [REWARDKIT, str(tests), "--workspace", str(tmp_path), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    details = json.loads((tmp_path / "reward-details.json").read_text())
    assert details["process"]["criteria"][0]["value"] == expected


def test_listing_only_the_stale_rows_no_longer_pays_like_the_answer(
    tmp_path: Path,
) -> None:
    """The pre-hardening deliverable, graded against the work product.

    Before ``notice_audit`` existed, this task asked for a conclusion:
    every scalar plus one five-item list. Nine of nine measured cells
    were precision-1.0 -- none ever submitted a false positive -- so
    under-claiming was the dominant strategy and the ceiling sat near the
    top. An agent that still stops at the stale references now files
    five rows of a thirteen-row schedule.

    Pinned to the measured figure rather than a comfortable threshold:
    0.6856 is what perfect work on the old task is worth once the audit
    carries the score, and a rebalance that moves it should have to say
    so out loud.
    """

    answer = _perfect()
    answer["notice_audit"] = [
        row for row in ORACLE["notice_audit"] if row["classification"] == "stale"
    ]

    scored = _grade(tmp_path, answer)["answer"]

    assert 0.67 < scored < 0.70, f"stale-only is worth 0.6856, measured {scored}"


def test_an_audit_that_contradicts_its_own_stale_list_earns_no_coherence(
    tmp_path: Path,
) -> None:
    """``stale_calendar_refs`` is a partition of the audit, not a rumour."""

    answer = _perfect()
    answer["stale_calendar_refs"] = answer["stale_calendar_refs"][:2]

    assert _grade(tmp_path, answer)["answer"] < 1.0


def test_a_current_row_cannot_name_a_superseded_date(tmp_path: Path) -> None:
    """Classification and the two dates on the row have to agree."""

    answer = _perfect()
    for row in answer["notice_audit"]:
        if row["classification"] == "stale":
            row["classification"] = "current"
            break

    assert _grade(tmp_path, answer)["answer"] < 1.0
