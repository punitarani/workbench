"""Synthetic contract tests for the standard-drift verifier."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

TASK = Path(__file__).parent
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
TRUTH = json.loads((TESTS / "ground_truth.json").read_text())
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return {
        "playbook_path": TRUTH["playbook_path"],
        "ndas": deepcopy(TRUTH["ndas"]),
        "silent_versions": deepcopy(TRUTH["silent_versions"]),
        "term": {
            "playbook_standard": "three years",
            "practice": "five years",
            "document_path": TRUTH["clauses"]["term"]["document_path"],
            "version": TRUTH["clauses"]["term"]["version"],
            "date": TRUTH["clauses"]["term"]["date"],
        },
        "residuals": {
            "playbook_standard": "reject residual knowledge",
            "practice": "accepted residual knowledge",
            "document_path": TRUTH["clauses"]["residuals"]["document_path"],
            "version": TRUTH["clauses"]["residuals"]["version"],
            "date": TRUTH["clauses"]["residuals"]["date"],
        },
    }


def _grade(
    tmp_path: Path, answer: object | None, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "drift.json").write_text(raw)
    elif answer is not None:
        (workspace / "drift.json").write_text(json.dumps(answer, allow_nan=True))
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


def test_near_miss_is_partial_and_shotgun_is_worse(tmp_path: Path) -> None:
    near = _perfect()
    near["ndas"].pop(next(iter(near["ndas"])))
    shotgun = _perfect()
    shotgun["ndas"].update({f"/invented/{i}.md": "conforms" for i in range(50)})
    near_score = _grade(tmp_path / "near", near)["answer"]
    shotgun_score = _grade(tmp_path / "shotgun", shotgun)["answer"]
    assert 0.0 < shotgun_score < near_score < 1.0


def test_duplicate_is_an_extra_but_reordering_is_neutral(tmp_path: Path) -> None:
    duplicate = _perfect()
    duplicate["silent_versions"].append(duplicate["silent_versions"][0])
    reordered = _perfect()
    reordered["silent_versions"].reverse()
    reordered["ndas"] = dict(reversed(list(reordered["ndas"].items())))
    assert 0.0 < _grade(tmp_path / "dup", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "order", reordered)["answer"] == 1.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "numeric_path",
        "bool_version",
        "numeric_id",
        "bad_status",
        "nonfinite",
    ],
)
def test_malformed_or_type_invalid_contract_scores_zero(
    tmp_path: Path, mutation: str
) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["private"] = True
    elif mutation == "missing":
        answer.pop("term")
    elif mutation == "numeric_path":
        answer["playbook_path"] = 9
    elif mutation == "bool_version":
        answer["term"]["version"] = True
    elif mutation == "numeric_id":
        answer["silent_versions"][0] = 11
    elif mutation == "bad_status":
        answer["ndas"][next(iter(answer["ndas"]))] = "unknown"
    else:
        answer["term"]["version"] = float("nan")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "malformed", None, "{")["answer"] == 0.0
    assert _grade(tmp_path / "oversized", None, " " * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "truth.json"
    (workspace / "drift.json").symlink_to(target)
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
        ({"function_name": "imanage__get_document_versions"}, 1.0),
        (
            {
                "function_name": "exec",
                "arguments": {
                    "input": "await tools.imanage__get_document_versions({})"
                },
            },
            1.0,
        ),
        (
            {
                "function_name": "exec",
                "arguments": {"input": "get_document_versions would help"},
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
        f"rk.tool_invoked('get_document_versions', path={str(trajectory)!r}, "
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
