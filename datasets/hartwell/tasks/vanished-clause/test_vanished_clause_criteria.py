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
pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


def _perfect() -> dict[str, object]:
    return {
        "document_path": T["document_path"],
        "dropped_clause": "indemnification protection",
        "dropped_in_version": T["dropped_in_version"],
        "author": "Marcus Liang",
        "date": T["date"],
        "change_comment": "conformed draft",
        "clean_documents": deepcopy(T["clean_documents"]),
        "unreviewed_revisions": deepcopy(T["unreviewed_revisions"]),
    }


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
