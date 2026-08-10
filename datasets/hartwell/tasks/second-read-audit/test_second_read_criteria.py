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
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return {
        "requests_reviewed": T["requests_reviewed"],
        "conversations_reviewed": T["conversations_reviewed"],
        "unanswered_request_ts": [
            prefix + ".001" for prefix in T["unanswered_request_ts_prefixes"]
        ],
        "unanswered_requests": [
            {
                "ts": record["ts_prefix"] + ".001",
                "date": record["date"],
                "asked_by": record["asked_by"],
                "asked_of": record["asked_of"],
            }
            for record in T["unanswered_requests"]
        ],
        "answered_same_day": T["answered_same_day"],
        "came_back_later": [
            prefix + ".001" for prefix in T["came_back_later_prefixes"]
        ],
        "unanswered_askers": [
            " ".join(marker.title() for marker in markers)
            for markers in T["asker_markers"]
        ],
    }


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
