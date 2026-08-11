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
ORACLE = json.loads((TESTS / "oracle.json").read_text())
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return deepcopy(ORACLE)


def test_committed_oracle_has_complete_version_audit() -> None:
    assert len(ORACLE["version_audit"]) == ORACLE["versions_reviewed"] == 16
    assert ORACLE["substantive_versions"] == 8
    assert ORACLE["notices_only_versions"] == 1
    assert ORACLE["unchanged_versions"] == 7
    assert ORACLE["covered_substantive_versions"] == 4
    assert ORACLE["silent_substantive_versions"] == 4
    assert ORACLE["covering_email_count"] == 4


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


def test_headline_only_work_product_cannot_reach_half_credit(tmp_path: Path) -> None:
    answer = _perfect()
    answer["version_audit"] = []

    assert 0.1 < _grade(tmp_path, answer)["answer"] < 0.5


def test_version_audit_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path,
) -> None:
    near = _perfect()
    near["version_audit"].pop()
    shotgun = _perfect()
    shotgun["version_audit"].extend(deepcopy(shotgun["version_audit"][:1]) * 30)
    duplicate = _perfect()
    duplicate["version_audit"].append(deepcopy(duplicate["version_audit"][0]))
    reordered = _perfect()
    reordered["version_audit"].reverse()

    near_score = _grade(tmp_path / "near", near)["answer"]
    assert 0.5 < near_score < 1.0
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score
    assert 0.5 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "reorder", reordered)["answer"] == 1.0


def test_wrong_or_duplicate_email_citation_loses_credit(tmp_path: Path) -> None:
    wrong = _perfect()
    covered = next(row for row in wrong["version_audit"] if row["email_ids"])
    covered["email_ids"].append("invented-message")
    duplicate = _perfect()
    covered = next(row for row in duplicate["version_audit"] if row["email_ids"])
    covered["email_ids"].append(covered["email_ids"][0])

    assert 0.5 < _grade(tmp_path / "wrong", wrong)["answer"] < 1.0
    assert 0.5 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0


def test_version_audit_reconciliation_is_graded_separately(tmp_path: Path) -> None:
    inconsistent = _perfect()
    inconsistent["substantive_versions"] -= 1

    score = _grade(tmp_path, inconsistent)["answer"]
    details = json.loads((tmp_path / "reward-details.json").read_text())
    criteria = {item["name"]: item["value"] for item in details["answer"]["criteria"]}

    assert 0.0 < score < 1.0
    assert criteria["version_audit_reconciles"] == 0.0


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
        "audit_not_list",
        "audit_extra_key",
        "audit_numeric_id",
        "audit_bad_class",
        "audit_numeric_email",
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
    elif mutation == "audit_not_list":
        answer["version_audit"] = {}
    elif mutation == "audit_extra_key":
        answer["version_audit"][0]["note"] = "invented"
    elif mutation == "audit_numeric_id":
        answer["version_audit"][0]["version_id"] = 11
    elif mutation == "audit_bad_class":
        answer["version_audit"][0]["change_class"] = "formatting"
    elif mutation == "audit_numeric_email":
        answer["version_audit"][0]["email_ids"] = [7]
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
