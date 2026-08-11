"""Synthetic contract tests for the second-read verifier."""

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
    return deepcopy(ORACLE)


def test_committed_oracle_has_complete_response_audit() -> None:
    assert len(ORACLE["response_audit"]) == ORACLE["requests_reviewed"] == 75
    assert ORACLE["answered_same_day"] == 67
    assert ORACLE["answered_next_working_day"] == 5
    assert ORACLE["unanswered_by_deadline"] == 3


def _grade(
    tmp_path: Path, answer: object | None, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "second-read.json").write_text(raw)
    elif answer is not None:
        (workspace / "second-read.json").write_text(json.dumps(answer, allow_nan=True))
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


@pytest.mark.parametrize(
    "field",
    [
        "unanswered_request_ts",
        "unanswered_requests",
        "came_back_later",
        "unanswered_askers",
    ],
)
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


def test_duplicate_nested_request_member_is_a_precision_error(tmp_path: Path) -> None:
    answer = _perfect()
    answer["unanswered_requests"].append(deepcopy(answer["unanswered_requests"][0]))
    assert 0.0 < _grade(tmp_path, answer)["answer"] < 1.0


def test_headline_only_work_product_cannot_reach_half_credit(tmp_path: Path) -> None:
    answer = _perfect()
    answer["response_audit"] = []

    assert 0.1 < _grade(tmp_path, answer)["answer"] < 0.5


def test_response_audit_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path,
) -> None:
    near = _perfect()
    near["response_audit"].pop()
    shotgun = _perfect()
    shotgun["response_audit"].extend(deepcopy(shotgun["response_audit"][:1]) * 50)
    duplicate = _perfect()
    duplicate["response_audit"].append(deepcopy(duplicate["response_audit"][0]))
    reordered = _perfect()
    reordered["response_audit"].reverse()

    near_score = _grade(tmp_path / "near", near)["answer"]
    assert 0.5 < near_score < 1.0
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score
    assert 0.5 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "reorder", reordered)["answer"] == 1.0


def test_wrong_first_response_identity_loses_credit(tmp_path: Path) -> None:
    wrong = _perfect()
    wrong["response_audit"][0]["first_response_id"] = "invented-response"

    assert 0.5 < _grade(tmp_path, wrong)["answer"] < 1.0


def test_response_audit_reconciliation_is_graded_separately(tmp_path: Path) -> None:
    inconsistent = _perfect()
    inconsistent["answered_same_day"] -= 1

    score = _grade(tmp_path, inconsistent)["answer"]
    details = json.loads((tmp_path / "reward-details.json").read_text())
    criteria = {item["name"]: item["value"] for item in details["answer"]["criteria"]}

    assert 0.0 < score < 1.0
    assert criteria["response_audit_reconciles"] == 0.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "bool_count",
        "numeric_ts",
        "numeric_name",
        "nested_extra",
        "numeric_date",
        "nonfinite",
        "audit_not_list",
        "audit_extra_key",
        "audit_numeric_ts",
        "audit_bad_surface",
        "audit_bad_outcome",
        "audit_missing_response_id",
    ],
)
def test_type_invalid_contract_scores_zero(tmp_path: Path, mutation: str) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["evidence"] = []
    elif mutation == "missing":
        answer.pop("answered_same_day")
    elif mutation == "bool_count":
        answer["requests_reviewed"] = True
    elif mutation == "numeric_ts":
        answer["unanswered_request_ts"][0] = 8253753
    elif mutation == "numeric_name":
        answer["unanswered_askers"][0] = 1
    elif mutation == "nested_extra":
        answer["unanswered_requests"][0]["id"] = "x"
    elif mutation == "numeric_date":
        answer["unanswered_requests"][0]["date"] = 20260605
    elif mutation == "audit_not_list":
        answer["response_audit"] = {}
    elif mutation == "audit_extra_key":
        answer["response_audit"][0]["note"] = "invented"
    elif mutation == "audit_numeric_ts":
        answer["response_audit"][0]["request_ts"] = 7
    elif mutation == "audit_bad_surface":
        answer["response_audit"][0]["first_response_surface"] = "clio"
    elif mutation == "audit_bad_outcome":
        answer["response_audit"][0]["outcome"] = "late"
    elif mutation == "audit_missing_response_id":
        answer["response_audit"][0]["first_response_id"] = ""
    else:
        answer["requests_reviewed"] = float("inf")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "bad", None, "{")["answer"] == 0.0
    assert _grade(tmp_path / "large", None, "x" * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "truth.json"
    (workspace / "second-read.json").symlink_to(target)
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
        ({"function_name": "slack__slack_read_channel"}, 1.0),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "await tools.slack__slack_read_channel({})"},
            },
            1.0,
        ),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "slack_read_channel would help"},
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
        f"rk.tool_invoked('slack_read_channel', path={str(trajectory)!r}, "
        "name='used')\n"
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
