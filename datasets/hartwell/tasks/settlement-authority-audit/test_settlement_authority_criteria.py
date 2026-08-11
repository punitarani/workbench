"""Adversarial verifier contracts for settlement-authority-audit."""

import json
import shutil
import subprocess
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import pytest

TASK = Path(__file__).parent
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return json.loads((TESTS / "oracle.json").read_text())


def _grade(
    tmp_path: Path, answer: object | None, *, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "authority.json").write_text(raw)
    elif answer is not None:
        (workspace / "authority.json").write_text(
            json.dumps(answer, allow_nan=True)
        )
    output = tmp_path / "reward.json"
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.read_text())


def test_exact_answer_has_only_answer_and_process(tmp_path: Path) -> None:
    assert _grade(tmp_path, _perfect()) == {"answer": 1.0, "process": 0.0}


@pytest.mark.parametrize(
    "field", ["breach_message_ids", "authority_timeline", "proposal_audit"]
)
def test_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path, field: str
) -> None:
    near = _perfect()
    near[field].pop()
    shotgun = _perfect()
    shotgun[field].extend(deepcopy(shotgun[field][:1]) * 12)
    duplicate = _perfect()
    duplicate[field].append(deepcopy(duplicate[field][0]))
    reordered = _perfect()
    reordered[field].reverse()
    near_score = _grade(tmp_path / "near", near)["answer"]
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score < 1.0
    assert 0.0 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "reordered", reordered)["answer"] == 1.0


def test_duplicate_nested_evidence_is_penalized_not_crashed(tmp_path: Path) -> None:
    answer = _perfect()
    answer["proposal_audit"][0]["authority_source_ids"].append(
        answer["proposal_audit"][0]["authority_source_ids"][0]
    )
    assert 0.0 < _grade(tmp_path, answer)["answer"] < 1.0


def test_equivalent_utc_timestamps_receive_full_credit(tmp_path: Path) -> None:
    answer = _perfect()
    for key in ("authority_timeline", "proposal_audit"):
        for record in answer[key]:
            for field in ("effective_at", "expires_at", "sent_at"):
                value = record.get(field)
                if value:
                    record[field] = datetime.fromisoformat(value).astimezone(
                        timezone.utc
                    ).isoformat()
    assert _grade(tmp_path, answer)["answer"] == 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "numeric_timestamp",
        "boolean_count",
        "unknown_enum",
        "nested_extra",
        "nonfinite",
    ],
)
def test_malformed_contract_scores_zero(tmp_path: Path, mutation: str) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["analysis"] = "trust me"
    elif mutation == "missing":
        answer.pop("matter_number")
    elif mutation == "numeric_timestamp":
        answer["proposal_audit"][0]["sent_at"] = 123
    elif mutation == "boolean_count":
        answer["proposal_count"] = True
    elif mutation == "unknown_enum":
        answer["proposal_audit"][0]["disposition"] = "close_enough"
    elif mutation == "nested_extra":
        answer["authority_timeline"][0]["memo"] = "hidden"
    else:
        answer["proposal_audit"][0]["amount_cents"] = float("nan")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "bad", None, raw="{")["answer"] == 0.0
    assert _grade(tmp_path / "large", None, raw="x" * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "oracle.json"
    (workspace / "authority.json").symlink_to(target)
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
                "arguments": {"input": "// tools.gmail__search_threads({})"},
            },
            0.0,
        ),
    ],
)
def test_process_detects_execution_not_mentions(
    tmp_path: Path, call: dict[str, object], expected: float
) -> None:
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(json.dumps({"steps": [{"tool_calls": [call]}]}))
    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TESTS / "criteria.py", tests / "criteria.py")
    (tests / "process" / "method.py").write_text(
        "import rewardkit as rk\n"
        f"rk.tool_invoked('search_threads', path={str(trajectory)!r}, name='used')\n"
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
