"""Synthetic contract tests for the visitor-log Reward Kit verifier."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

TASK = Path(__file__).parent
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")

type JsonObject = dict[str, object]

pytestmark = pytest.mark.skipif(
    REWARDKIT is None,
    reason="rewardkit not on PATH; uv tool install harbor-rewardkit[all]==0.1.7",
)


def _truth() -> JsonObject:
    return json.loads((TESTS / "oracle.json").read_text())


def _perfect() -> JsonObject:
    return deepcopy(_truth())


def test_committed_oracle_has_complete_custody_audit() -> None:
    truth = _truth()
    assert len(truth["custody_audit"]) == truth["requests_reviewed"] == 71
    assert truth["returned_same_day"] == 59
    assert truth["returned_next_working_day"] == 10
    assert truth["unresolved_by_followup"] == 2


def _grade(tmp_path: Path, answer: JsonObject | None) -> tuple[JsonObject, JsonObject]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if answer is not None:
        (workspace / "visitor-log.json").write_text(json.dumps(answer, indent=2))
    output = tmp_path / "logs" / "reward-raw.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        json.loads(output.read_text()),
        json.loads((output.parent / "reward-details.json").read_text()),
    )


def _criterion(details: JsonObject, dimension: str, name: str) -> float:
    for score in details[dimension]["criteria"]:
        if score["name"] == name:
            return score["value"]
    raise AssertionError(f"no criterion {name!r} in {dimension}")


def test_exact_answer_has_only_the_canonical_raw_dimensions(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, _perfect())
    assert reward == {"answer": 1.0, "process": 0.0}


def test_extra_top_level_or_nested_field_invalidates_public_contract(
    tmp_path: Path,
) -> None:
    top = _perfect()
    top["private_evidence"] = True
    top_reward, top_details = _grade(tmp_path / "top", top)

    nested = _perfect()
    breaches = nested["same_day_breaches"]
    assert isinstance(breaches, list) and isinstance(breaches[0], dict)
    breaches[0]["response_date"] = "2026-03-03"
    nested_reward, nested_details = _grade(tmp_path / "nested", nested)

    assert _criterion(top_details, "answer", "deliverable_format") == 0.0
    assert _criterion(nested_details, "answer", "deliverable_format") == 0.0
    assert top_reward == nested_reward == {"answer": 0.0, "process": 0.0}


def test_dangling_agent_symlink_that_resolves_under_verifier_is_rejected(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    simulated_verifier_truth = (
        tmp_path / "verifier-mount" / "tests" / "ground_truth.json"
    )
    deliverable = workspace / "visitor-log.json"
    deliverable.symlink_to(simulated_verifier_truth)
    assert deliverable.is_symlink() and not deliverable.exists()

    simulated_verifier_truth.parent.mkdir(parents=True)
    shutil.copyfile(TESTS / "ground_truth.json", simulated_verifier_truth)
    assert deliverable.exists()
    output = tmp_path / "logs" / "reward-raw.json"
    output.parent.mkdir(parents=True)

    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(output.read_text()) == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize(
    "mutation",
    [
        "boolean_count",
        "float_count",
        "numeric_breach_ts",
        "numeric_partition_ts",
        "numeric_unresolved_ts",
        "numeric_record_ts",
        "numeric_record_name",
        "invalid_resolution",
        "records_not_a_list",
        "malformed_record_member",
        "timestamps_not_a_list",
        "audit_not_a_list",
        "audit_extra_field",
        "numeric_request_ts",
        "invalid_return_surface",
        "invalid_outcome",
        "missing_return_id",
        "none_surface_with_return",
    ],
)
def test_type_invalid_public_contract_scores_zero(
    tmp_path: Path, mutation: str
) -> None:
    answer = _perfect()
    breaches = answer["same_day_breaches"]
    assert isinstance(breaches, list) and isinstance(breaches[0], dict)
    audit = answer["custody_audit"]
    assert isinstance(audit, list) and isinstance(audit[0], dict)
    if mutation == "boolean_count":
        answer["requests_reviewed"] = True
    elif mutation == "float_count":
        answer["returned_same_day"] = 59.0
    elif mutation == "numeric_breach_ts":
        answer["same_day_breach_ts"][0] = 60299.000029
    elif mutation == "numeric_partition_ts":
        answer["returned_next_working_day_ts"][0] = 60299.000029
    elif mutation == "numeric_unresolved_ts":
        answer["unresolved_ts"][0] = 7456314.002498
    elif mutation == "numeric_record_ts":
        breaches[0]["ts"] = 60299.000029
    elif mutation == "numeric_record_name":
        breaches[0]["asked_by"] = 1
    elif mutation == "invalid_resolution":
        breaches[0]["resolution"] = "same_day"
    elif mutation == "records_not_a_list":
        answer["same_day_breaches"] = {}
    elif mutation == "malformed_record_member":
        breaches[0] = "not a record"
    elif mutation == "timestamps_not_a_list":
        answer["same_day_breach_ts"] = {}
    elif mutation == "audit_not_a_list":
        answer["custody_audit"] = {}
    elif mutation == "audit_extra_field":
        audit[0]["private_note"] = "hidden"
    elif mutation == "numeric_request_ts":
        audit[0]["request_ts"] = 60299.000029
    elif mutation == "invalid_return_surface":
        audit[0]["first_return_surface"] = "teams"
    elif mutation == "invalid_outcome":
        audit[0]["outcome"] = "eventual"
    elif mutation == "missing_return_id":
        audit[0]["first_return_surface"] = "slack"
        audit[0]["first_return_id"] = ""
    else:
        audit[0]["first_return_surface"] = "none"
        audit[0]["first_return_id"] = "invented"
        audit[0]["first_return_at"] = "2026-03-02T12:00:00-08:00"

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "deliverable_format") == 0.0
    assert reward == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize("key", ["same_day_breach_ts", "same_day_breaches"])
def test_duplicate_breach_member_is_counted_as_an_extra(
    tmp_path: Path, key: str
) -> None:
    answer = _perfect()
    values = answer[key]
    assert isinstance(values, list)
    values.append(deepcopy(values[0]))
    reward, details = _grade(tmp_path, answer)
    criterion_name = "breach_ts" if key.endswith("_ts") else "breaches"

    assert _criterion(details, "answer", f"{criterion_name}.f1") == pytest.approx(
        24 / 25, abs=1e-4
    )
    assert _criterion(details, "answer", f"{criterion_name}.certified") == 0.0
    assert reward["answer"] < 0.97


def test_headline_only_work_product_cannot_reach_half_credit(tmp_path: Path) -> None:
    answer = _perfect()
    answer["custody_audit"] = []

    reward, _ = _grade(tmp_path, answer)
    assert 0.1 < reward["answer"] < 0.5


def test_custody_audit_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path,
) -> None:
    near = _perfect()
    near["custody_audit"].pop()
    shotgun = _perfect()
    shotgun["custody_audit"].extend(deepcopy(shotgun["custody_audit"][:1]) * 50)
    duplicate = _perfect()
    duplicate["custody_audit"].append(deepcopy(duplicate["custody_audit"][0]))
    reordered = _perfect()
    reordered["custody_audit"].reverse()

    near_reward, _ = _grade(tmp_path / "near", near)
    shotgun_reward, _ = _grade(tmp_path / "shotgun", shotgun)
    duplicate_reward, _ = _grade(tmp_path / "duplicate", duplicate)
    reordered_reward, _ = _grade(tmp_path / "reorder", reordered)
    assert 0.5 < near_reward["answer"] < 1.0
    assert shotgun_reward["answer"] < near_reward["answer"]
    assert 0.5 < duplicate_reward["answer"] < 1.0
    assert reordered_reward["answer"] == 1.0


def test_wrong_first_return_identity_loses_credit(tmp_path: Path) -> None:
    wrong = _perfect()
    wrong["custody_audit"][0]["first_return_id"] = "invented-return"

    reward, _ = _grade(tmp_path, wrong)
    assert 0.5 < reward["answer"] < 1.0


def test_custody_audit_reconciliation_is_graded_separately(tmp_path: Path) -> None:
    inconsistent = _perfect()
    inconsistent["returned_same_day"] -= 1

    reward, details = _grade(tmp_path, inconsistent)

    assert 0.0 < reward["answer"] < 1.0
    assert _criterion(details, "answer", "custody_audit_reconciles") == 0.0


def test_reordering_all_sets_keeps_full_credit(tmp_path: Path) -> None:
    answer = _perfect()
    for key in (
        "same_day_breach_ts",
        "same_day_breaches",
        "returned_next_working_day_ts",
        "unresolved_ts",
        "custody_audit",
    ):
        values = answer[key]
        assert isinstance(values, list)
        values.reverse()

    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 1.0, "process": 0.0}


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, None)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_near_miss_uses_ninety_ten_scoring_for_every_affected_set(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["same_day_breach_ts"] = answer["same_day_breach_ts"][:-1]
    answer["same_day_breaches"] = answer["same_day_breaches"][:-1]
    answer["returned_next_working_day_ts"] = answer["returned_next_working_day_ts"][:-1]
    reward, details = _grade(tmp_path, answer)

    for name in ("breach_ts", "breaches"):
        assert _criterion(details, "answer", f"{name}.f1") == pytest.approx(
            22 / 23, abs=1e-4
        )
        assert _criterion(details, "answer", f"{name}.certified") == 0.0
    assert _criterion(details, "answer", "next_working_day.f1") == pytest.approx(
        18 / 19, abs=1e-4
    )
    assert _criterion(details, "answer", "next_working_day.certified") == 0.0
    assert 0.85 < reward["answer"] < 0.95


def test_shotgun_custody_records_score_below_half(tmp_path: Path) -> None:
    answer = _perfect()
    for index in range(200):
        ts = f"99{index:04d}.999999"
        answer["custody_audit"].append(
            {
                "request_ts": ts,
                "request_date": "2026-07-01",
                "asked_by": f"Decoy {index}",
                "asked_of": "Nobody",
                "first_return_surface": "none",
                "first_return_id": "",
                "first_return_at": "",
                "outcome": "unresolved",
            }
        )
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "custody_audit.f1") == pytest.approx(
        142 / 342, abs=1e-4
    )
    assert 0.4 < reward["answer"] < 0.5


@pytest.mark.parametrize("contents", ["{not json", "[]", '"answer"'])
def test_malformed_deliverable_scores_zero(tmp_path: Path, contents: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "visitor-log.json").write_text(contents)
    output = tmp_path / "logs" / "reward-raw.json"
    output.parent.mkdir(parents=True)
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(output.read_text()) == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_deliverable_scores_zero(tmp_path: Path, nonfinite: float) -> None:
    answer = _perfect()
    answer["returned_same_day"] = nonfinite
    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_oversized_deliverable_scores_zero_without_crashing(tmp_path: Path) -> None:
    answer = _perfect()
    answer["padding"] = "x" * 1_100_000
    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 0.0, "process": 0.0}


def _trajectory(tmp_path: Path, name: str, steps: list[JsonObject]) -> Path:
    path = tmp_path / f"{name}.json"
    path.write_text(json.dumps({"steps": steps}))
    return path


NATIVE_CALL = {"function_name": "slack__slack_read_channel"}
UNIFIED_CALL = {
    "function_name": "exec",
    "arguments": {
        "input": "const r = await tools.slack__slack_read_channel({channel_id:'c1'});"
    },
}
SILENT_CALL = {"function_name": "exec", "arguments": {"input": "text(ALL_TOOLS)"}}
MENTION_CALL = {
    "function_name": "exec",
    "arguments": {"input": "The slack_read_channel tool would be useful here."},
}


def _process_only(tmp_path: Path, trajectory: Path) -> JsonObject:
    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TESTS / "criteria.py", tests / "criteria.py")
    (tests / "process" / "method.py").write_text(
        "import rewardkit as rk\n"
        f"rk.tool_invoked('slack_read_channel', path={str(trajectory)!r},"
        " name='ours')\n"
        f"rk.trajectory_tool_used('slack__slack_read_channel',"
        f" path={str(trajectory)!r}, name='builtin')\n"
    )
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = tmp_path / "reward-raw.json"
    subprocess.run(
        [REWARDKIT, str(tests), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    details = json.loads((output.parent / "reward-details.json").read_text())
    return {
        criterion["name"]: criterion["value"]
        for criterion in details["process"]["criteria"]
    }


@pytest.mark.parametrize(
    ("name", "call", "ours", "builtin"),
    [
        ("native", NATIVE_CALL, 1.0, 1.0),
        ("unified", UNIFIED_CALL, 1.0, 0.0),
        ("silent", SILENT_CALL, 0.0, 0.0),
        ("mention", MENTION_CALL, 0.0, 0.0),
    ],
)
def test_tool_invoked_reads_native_and_actual_unified_exec_calls(
    tmp_path: Path, name: str, call: JsonObject, ours: float, builtin: float
) -> None:
    trajectory = _trajectory(
        tmp_path, name, [{"source": "agent", "tool_calls": [call]}]
    )
    scores = _process_only(tmp_path, trajectory)
    assert scores["ours"] == ours
    assert scores["builtin"] == builtin
