"""Synthetic contract tests for the vanished-clause verifier."""

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
    answer = deepcopy(ORACLE)
    answer["dropped_clause"] = "indemnification protection"
    answer["author"] = "Marcus Liang"
    answer["change_comment"] = "conformed draft"
    return answer


def test_committed_oracle_has_complete_revision_ledger() -> None:
    assert len(ORACLE["revision_audit"]) == ORACLE["revisions_reviewed"] == 57
    assert ORACLE["covered_revisions"] == 52
    assert ORACLE["unreviewed_revision_count"] == 5
    assert ORACLE["covering_communications"] == 53


def _grade(
    tmp_path: Path, answer: object | None, raw: str | None = None
) -> dict[str, float]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    if raw is not None:
        (workspace / "clause.json").write_text(raw)
    elif answer is not None:
        (workspace / "clause.json").write_text(json.dumps(answer, allow_nan=True))
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


@pytest.mark.parametrize("field", ["clean_documents", "unreviewed_revisions"])
def test_sets_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path, field: str
) -> None:
    near = _perfect()
    near[field].pop()
    shotgun = _perfect()
    shotgun[field].extend(deepcopy(shotgun[field][:1]) * 40)
    duplicate = _perfect()
    duplicate[field].append(deepcopy(duplicate[field][0]))
    reordered = _perfect()
    reordered[field].reverse()
    near_score = _grade(tmp_path / "near", near)["answer"]
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score < 1.0
    assert 0.0 < _grade(tmp_path / "dup", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "order", reordered)["answer"] == 1.0


def test_headline_only_work_product_cannot_reach_half_credit(tmp_path: Path) -> None:
    answer = _perfect()
    answer["revision_audit"] = []

    score = _grade(tmp_path, answer)["answer"]

    assert 0.1 < score < 0.5


def test_revision_ledger_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path,
) -> None:
    near = _perfect()
    near["revision_audit"].pop()
    shotgun = _perfect()
    shotgun["revision_audit"].extend(deepcopy(shotgun["revision_audit"][:1]) * 40)
    duplicate = _perfect()
    duplicate["revision_audit"].append(deepcopy(duplicate["revision_audit"][0]))
    reordered = _perfect()
    reordered["revision_audit"].reverse()
    for row in reordered["revision_audit"]:
        row["email_ids"].reverse()
        row["public_slack_ts"].reverse()

    near_score = _grade(tmp_path / "near", near)["answer"]
    assert 0.5 < near_score < 1.0
    assert _grade(tmp_path / "shotgun", shotgun)["answer"] < near_score
    assert 0.5 < _grade(tmp_path / "duplicate", duplicate)["answer"] < 1.0
    assert _grade(tmp_path / "reordered", reordered)["answer"] == 1.0


def test_wrong_or_duplicate_nested_citation_loses_credit(tmp_path: Path) -> None:
    wrong = _perfect()
    covered = next(
        row
        for row in wrong["revision_audit"]
        if row["email_ids"] or row["public_slack_ts"]
    )
    citations = covered["email_ids"] or covered["public_slack_ts"]
    citations.append("invented-evidence")
    duplicate = _perfect()
    covered = next(
        row
        for row in duplicate["revision_audit"]
        if row["email_ids"] or row["public_slack_ts"]
    )
    citations = covered["email_ids"] or covered["public_slack_ts"]
    citations.append(citations[0])

    wrong_score = _grade(tmp_path / "wrong", wrong)["answer"]
    duplicate_score = _grade(tmp_path / "duplicate", duplicate)["answer"]
    assert 0.5 < wrong_score < 1.0
    assert 0.5 < duplicate_score < 1.0


def test_ledger_reconciliation_is_graded_separately(tmp_path: Path) -> None:
    inconsistent = _perfect()
    inconsistent["covered_revisions"] -= 1

    details_path = tmp_path / "reward-details.json"
    score = _grade(tmp_path, inconsistent)["answer"]
    details = json.loads(details_path.read_text())
    criteria = {item["name"]: item["value"] for item in details["answer"]["criteria"]}

    assert 0.0 < score < 1.0
    assert criteria["ledger_reconciles"] == 0.0


@pytest.mark.parametrize(
    "mutation",
    [
        "extra",
        "missing",
        "bool_version",
        "string_number",
        "numeric_revision",
        "numeric_date",
        "nonfinite",
        "ledger_not_list",
        "ledger_extra_key",
        "ledger_wrong_number",
        "ledger_wrong_status",
        "ledger_numeric_email",
        "ledger_numeric_slack",
    ],
)
def test_type_invalid_contract_scores_zero(tmp_path: Path, mutation: str) -> None:
    answer = _perfect()
    if mutation == "extra":
        answer["evidence"] = []
    elif mutation == "missing":
        answer.pop("author")
    elif mutation == "bool_version":
        answer["dropped_in_version"] = True
    elif mutation == "string_number":
        answer["clean_documents"][0] = "1"
    elif mutation == "numeric_revision":
        answer["unreviewed_revisions"][0] = 4
    elif mutation == "numeric_date":
        answer["date"] = 20260521
    elif mutation == "ledger_not_list":
        answer["revision_audit"] = {}
    elif mutation == "ledger_extra_key":
        answer["revision_audit"][0]["note"] = "invented"
    elif mutation == "ledger_wrong_number":
        answer["revision_audit"][0]["document_number"] = "21"
    elif mutation == "ledger_wrong_status":
        answer["revision_audit"][0]["coverage_status"] = "late"
    elif mutation == "ledger_numeric_email":
        answer["revision_audit"][0]["email_ids"] = [7]
    elif mutation == "ledger_numeric_slack":
        answer["revision_audit"][0]["public_slack_ts"] = [7]
    else:
        answer["dropped_in_version"] = float("nan")
    assert _grade(tmp_path, answer) == {"answer": 0.0, "process": 0.0}


def test_missing_malformed_oversized_and_symlink_score_zero(tmp_path: Path) -> None:
    assert _grade(tmp_path / "missing", None)["answer"] == 0.0
    assert _grade(tmp_path / "bad", None, "{")["answer"] == 0.0
    assert _grade(tmp_path / "large", None, "x" * 1_000_001)["answer"] == 0.0
    workspace = tmp_path / "link" / "workspace"
    workspace.mkdir(parents=True)
    target = tmp_path / "verifier" / "truth.json"
    (workspace / "clause.json").symlink_to(target)
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
