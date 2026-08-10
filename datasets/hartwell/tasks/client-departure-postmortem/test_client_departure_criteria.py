"""Synthetic contract tests for the client-departure verifier."""

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
        "first_negative_signal_date": T["first_negative_signal_date"],
        "first_negative_signal_ts": T["first_negative_signal_ts_prefix"] + "001367",
        "happy_update_ts": T["happy_update_ts_prefix"] + "000633",
        "happy_update_reactions": T["happy_update_reactions"],
        "first_negative_signal_reactions": T["first_negative_signal_reactions"],
        "reaction_trajectory": deepcopy(T["reaction_trajectory"]),
        "matter_closed_date": T["matter_closed_date"],
        "termination_email_date": T["termination_email_date"],
        "disengagement_letter_path": "/" + T["letter_path_suffix"],
        "unanswered_client_emails": deepcopy(T["unanswered_client_emails"]),
    }


def _grade(
    tmp_path: Path, answer: object | None, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "postmortem.json").write_text(raw)
    elif answer is not None:
        (workspace / "postmortem.json").write_text(json.dumps(answer, allow_nan=True))
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


def test_set_near_miss_shotgun_duplicate_and_reorder(tmp_path: Path) -> None:
    near = _perfect()
    near["unanswered_client_emails"].pop()
    shotgun = _perfect()
    shotgun["unanswered_client_emails"].extend(f"msg-fake-{i}" for i in range(30))
    duplicate = _perfect()
    duplicate["unanswered_client_emails"].append(
        duplicate["unanswered_client_emails"][0]
    )
    reordered = _perfect()
    reordered["unanswered_client_emails"].reverse()
    near_score = _grade(tmp_path / "near", near)["answer"]
    assert 0.0 < _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score < 1.0
    assert 0.0 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "reordered", reordered)["answer"] == 1.0


def test_reaction_trajectory_remains_ordered_and_position_aware(tmp_path: Path) -> None:
    answer = _perfect()
    answer["reaction_trajectory"].reverse()
    score = _grade(tmp_path, answer)["answer"]
    assert 0.92 < score < 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "numeric_ts",
        "bool_count",
        "numeric_id",
        "string_reaction",
        "nonfinite",
    ],
)
def test_type_invalid_contract_scores_zero(tmp_path: Path, mutation: str) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["evidence"] = []
    elif mutation == "missing":
        answer.pop("matter_closed_date")
    elif mutation == "numeric_ts":
        answer["happy_update_ts"] = 1960800
    elif mutation == "bool_count":
        answer["happy_update_reactions"] = True
    elif mutation == "numeric_id":
        answer["unanswered_client_emails"][0] = 311
    elif mutation == "string_reaction":
        answer["reaction_trajectory"][0] = "3"
    else:
        answer["reaction_trajectory"][0] = float("inf")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "bad", None, "[")["answer"] == 0.0
    assert _grade(tmp_path / "large", None, "x" * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "truth.json"
    (workspace / "postmortem.json").symlink_to(target)
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
        ({"function_name": "gmail__search_threads"}, 1.0),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "await tools.gmail__search_threads({})"},
            },
            1.0,
        ),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "search_threads would help"},
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
        f"rk.tool_invoked('search_threads', path={str(trajectory)!r}, "
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
