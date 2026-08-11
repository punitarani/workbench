"""Synthetic contract tests for the billing-hygiene Reward Kit verifier."""

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


def test_committed_oracle_has_complete_daily_review() -> None:
    truth = _truth()
    review = truth["daily_review"]
    assert len(review) == truth["person_days_reviewed"] == 655
    assert sum(len(row["billable_entry_ids"]) for row in review) == 4233
    dispositions = {
        name: sum(row["disposition"] == name for row in review)
        for name in (
            "cleared_by_communication",
            "cleared_no_corroboration",
            "anomalous",
        )
    }
    assert dispositions == {
        "cleared_by_communication": 637,
        "cleared_no_corroboration": 15,
        "anomalous": 3,
    }


def _grade(tmp_path: Path, answer: JsonObject | None) -> tuple[JsonObject, JsonObject]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if answer is not None:
        (workspace / "hygiene.json").write_text(json.dumps(answer, indent=2))
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


@pytest.mark.parametrize(
    ("extra_key", "extra_value"),
    [
        ("unexpected", True),
        ("unsupported_entry_ids", [1318, 1319]),
    ],
)
def test_extra_top_level_field_invalidates_public_contract(
    tmp_path: Path, extra_key: str, extra_value: object
) -> None:
    answer = _perfect()
    answer[extra_key] = extra_value
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "deliverable_format") == 0.0
    assert reward == {"answer": 0.0, "process": 0.0}


def test_extra_anomalous_day_key_invalidates_public_contract(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    days[0]["unsupported_entries"] = []
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "deliverable_format") == 0.0
    assert reward == {"answer": 0.0, "process": 0.0}


def test_dangling_agent_symlink_that_resolves_under_verifier_is_rejected(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    simulated_verifier_truth = (
        tmp_path / "verifier-mount" / "tests" / "ground_truth.json"
    )
    deliverable = workspace / "hygiene.json"
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
        "numeric_string_count",
        "boolean_aggregate",
        "numeric_date",
        "numeric_timekeeper",
        "string_entry_id",
        "numeric_matter",
        "boolean_minutes",
        "string_billed_cents",
        "string_phantom_note_id",
        "review_not_a_list",
        "review_extra_field",
        "numeric_review_date",
        "string_billable_entry_id",
        "numeric_gmail_id",
        "numeric_slack_ts",
        "string_corroborated_entry_id",
        "numeric_corroborated_matter",
        "invalid_disposition",
    ],
)
def test_type_invalid_public_contract_scores_zero(
    tmp_path: Path, mutation: str
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    phantom_ids = answer["phantom_note_ids"]
    review = answer["daily_review"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    assert isinstance(phantom_ids, list)
    assert isinstance(review, list) and isinstance(review[0], dict)
    if mutation == "numeric_string_count":
        answer["entries_reviewed"] = str(answer["entries_reviewed"])
    elif mutation == "boolean_aggregate":
        answer["anomalous_entry_count"] = True
    elif mutation == "numeric_date":
        days[0]["date"] = 20260404
    elif mutation == "numeric_timekeeper":
        days[0]["timekeeper"] = 1
    elif mutation == "string_entry_id":
        days[0]["entry_ids"][0] = str(days[0]["entry_ids"][0])
    elif mutation == "numeric_matter":
        days[0]["matter_numbers"][0] = 1
    elif mutation == "boolean_minutes":
        days[0]["minutes"] = False
    elif mutation == "string_billed_cents":
        days[0]["billed_cents"] = str(days[0]["billed_cents"])
    elif mutation == "string_phantom_note_id":
        phantom_ids[0] = str(phantom_ids[0])
    elif mutation == "review_not_a_list":
        answer["daily_review"] = {}
    elif mutation == "review_extra_field":
        review[0]["private_note"] = "hidden"
    elif mutation == "numeric_review_date":
        review[0]["date"] = 20260302
    elif mutation == "string_billable_entry_id":
        review[0]["billable_entry_ids"][0] = "1"
    elif mutation == "numeric_gmail_id":
        row = next(row for row in review if row["sent_gmail_ids"])
        row["sent_gmail_ids"][0] = 1
    elif mutation == "numeric_slack_ts":
        row = next(row for row in review if row["sent_slack_ts"])
        row["sent_slack_ts"][0] = 1
    elif mutation == "string_corroborated_entry_id":
        row = next(row for row in review if row["corroborated_entry_ids"])
        row["corroborated_entry_ids"][0] = "1"
    elif mutation == "numeric_corroborated_matter":
        row = next(row for row in review if row["corroborated_matter_numbers"])
        row["corroborated_matter_numbers"][0] = 1
    else:
        review[0]["disposition"] = "uncertain"

    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_duplicate_anomalous_day_is_counted_as_an_extra_record(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    assert isinstance(days, list)
    days.append(deepcopy(days[0]))
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "anomalous_days.f1") == pytest.approx(
        6 / 7, abs=1e-4
    )
    assert _criterion(details, "answer", "anomalous_days.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.88 + 0.054 * (6 / 7), abs=1e-4)


@pytest.mark.parametrize("nested_key", ["entry_ids", "matter_numbers"])
def test_duplicate_nested_anomalous_day_member_loses_certification(
    tmp_path: Path, nested_key: str
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    members = days[0][nested_key]
    assert isinstance(members, list)
    members.append(members[0])
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "anomalous_days.f1") == pytest.approx(
        2 / 3, abs=1e-4
    )
    assert _criterion(details, "answer", "anomalous_days.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.88 + 0.054 * (2 / 3), abs=1e-4)


def test_duplicate_phantom_note_id_is_counted_as_an_extra(tmp_path: Path) -> None:
    answer = _perfect()
    note_ids = answer["phantom_note_ids"]
    assert isinstance(note_ids, list)
    note_ids.append(note_ids[0])

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "phantom_notes.f1") == pytest.approx(
        2 / 3, abs=1e-4
    )
    assert _criterion(details, "answer", "phantom_notes.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.96 + 0.036 * (2 / 3), abs=1e-4)


def test_reordering_records_and_nested_members_keeps_full_credit(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    assert isinstance(days, list)
    days.reverse()
    for day in days:
        assert isinstance(day, dict)
        for nested_key in ("entry_ids", "matter_numbers"):
            members = day[nested_key]
            assert isinstance(members, list)
            members.reverse()
    review = answer["daily_review"]
    assert isinstance(review, list)
    review.reverse()
    for record in review:
        assert isinstance(record, dict)
        for nested_key in (
            "billable_entry_ids",
            "sent_gmail_ids",
            "sent_slack_ts",
            "corroborated_entry_ids",
            "corroborated_matter_numbers",
        ):
            members = record[nested_key]
            assert isinstance(members, list)
            members.reverse()

    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 1.0, "process": 0.0}


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, None)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_headline_only_work_product_cannot_reach_half_credit(tmp_path: Path) -> None:
    answer = _perfect()
    answer["daily_review"] = []

    reward, _ = _grade(tmp_path, answer)
    assert 0.1 < reward["answer"] < 0.5


def test_daily_review_near_miss_shotgun_duplicate_and_reorder(
    tmp_path: Path,
) -> None:
    near = _perfect()
    near["daily_review"].pop()
    shotgun = _perfect()
    shotgun["daily_review"] = deepcopy(shotgun["daily_review"][:100])
    shotgun["daily_review"].extend(
        {
            "date": "2026-07-01",
            "timekeeper": f"Decoy {index}",
            "billable_entry_ids": [10_000 + index],
            "sent_gmail_ids": [],
            "sent_slack_ts": [],
            "corroborated_entry_ids": [],
            "corroborated_matter_numbers": [],
            "disposition": "cleared_no_corroboration",
        }
        for index in range(500)
    )
    duplicate = _perfect()
    duplicate["daily_review"].append(deepcopy(duplicate["daily_review"][0]))
    reordered = _perfect()
    reordered["daily_review"].reverse()

    near_reward, _ = _grade(tmp_path / "near", near)
    shotgun_reward, _ = _grade(tmp_path / "shotgun", shotgun)
    duplicate_reward, _ = _grade(tmp_path / "duplicate", duplicate)
    reordered_reward, _ = _grade(tmp_path / "reorder", reordered)
    assert 0.5 < near_reward["answer"] < 1.0
    assert shotgun_reward["answer"] < 0.5
    assert 0.5 < duplicate_reward["answer"] < 1.0
    assert reordered_reward["answer"] == 1.0


def test_wrong_communication_evidence_loses_credit(tmp_path: Path) -> None:
    wrong = _perfect()
    row = next(row for row in wrong["daily_review"] if row["sent_slack_ts"])
    row["sent_slack_ts"][0] = "invented-message"

    reward, _ = _grade(tmp_path, wrong)
    assert 0.5 < reward["answer"] < 1.0


def test_daily_review_reconciliation_is_graded_separately(tmp_path: Path) -> None:
    inconsistent = _perfect()
    inconsistent["cleared_by_communication"] -= 1

    reward, details = _grade(tmp_path, inconsistent)

    assert 0.0 < reward["answer"] < 1.0
    assert _criterion(details, "answer", "daily_review_reconciles") == 0.0


def test_near_miss_uses_ninety_ten_scoring_for_anomalous_days(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["anomalous_timekeeper_days"] = answer["anomalous_timekeeper_days"][:-1]
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "anomalous_days.f1") == pytest.approx(0.8)
    assert _criterion(details, "answer", "anomalous_days.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.88 + 0.054 * 0.8, abs=1e-4)


def test_phantom_note_set_also_uses_ninety_ten_scoring(tmp_path: Path) -> None:
    answer = _perfect()
    answer["phantom_note_ids"] = [176, 999]
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "phantom_notes.f1") == pytest.approx(
        2 / 3, abs=1e-4
    )
    assert _criterion(details, "answer", "phantom_notes.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.96 + 0.036 * (2 / 3), abs=1e-4)


def test_shotgun_summary_days_lose_summary_and_reconciliation_credit(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["anomalous_timekeeper_days"].extend(
        {
            "date": f"2026-07-{index:02d}",
            "timekeeper": f"Person {index}",
            "entry_ids": [5000 + index],
            "matter_numbers": [f"999{index:02d}-Decoy"],
            "minutes": index,
            "billed_cents": index,
        }
        for index in range(1, 31)
    )
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "anomalous_days.f1") == pytest.approx(
        1 / 6, abs=1e-4
    )
    assert _criterion(details, "answer", "anomalous_days.certified") == 0.0
    assert _criterion(details, "answer", "daily_review_reconciles") == 0.0
    assert 0.85 < reward["answer"] < 0.95


@pytest.mark.parametrize("contents", ["{not json", "[]", '"answer"'])
def test_malformed_deliverable_scores_zero(tmp_path: Path, contents: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "hygiene.json").write_text(contents)
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
    answer["anomalous_billed_cents_total"] = nonfinite
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
