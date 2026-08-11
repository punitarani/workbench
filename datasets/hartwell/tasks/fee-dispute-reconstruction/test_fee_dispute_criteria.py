"""Synthetic contract tests for the fee-dispute Reward Kit verifier."""

import json
import shutil
import subprocess
from copy import deepcopy
from pathlib import Path

import pytest

TASK = Path(__file__).parent
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
TRUTH = json.loads((TESTS / "oracle.json").read_text())
MARKERS = json.loads((TESTS / "ground_truth.json").read_text())

type JsonObject = dict[str, object]

pytestmark = pytest.mark.skipif(
    REWARDKIT is None,
    reason="rewardkit not on PATH; uv tool install harbor-rewardkit[all]==0.1.7",
)


def _perfect() -> JsonObject:
    timekeepers = [
        " ".join(marker.title() for marker in markers)
        for markers in MARKERS["timekeeper_markers"]
    ]
    return {
        "cutoff_date": TRUTH["cutoff_date"],
        "total_minutes": TRUTH["total_minutes"],
        "entry_count": TRUTH["entry_count"],
        "entries": deepcopy(TRUTH["entries"]),
        "minutes_by_timekeeper": {
            timekeeper: expected[1]
            for timekeeper, expected in zip(
                timekeepers, MARKERS["minutes_by_timekeeper_markers"], strict=True
            )
        },
        "timekeepers": timekeepers,
        "challenged_by": " ".join(
            marker.title() for marker in MARKERS["challenged_by_markers"]
        ),
        "challenge_date": TRUTH["challenge_date"],
        "support_audit": deepcopy(TRUTH["support_audit"]),
        "unsupported_days": deepcopy(TRUTH["unsupported_days"]),
    }


def _grade(tmp_path: Path, answer: JsonObject | None) -> tuple[JsonObject, JsonObject]:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    if answer is not None:
        (workspace / "dispute.json").write_text(json.dumps(answer, indent=2))
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


def _criterion(details: JsonObject, name: str) -> float:
    for score in details["answer"]["criteria"]:
        if score["name"] == name:
            return score["value"]
    raise AssertionError(f"no criterion {name!r} in answer")


def test_exact_answer_has_only_the_canonical_raw_dimensions(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, _perfect())
    assert set(reward) == {"answer", "process"}
    assert reward == {"answer": 1.0, "process": 0.0}


def test_extra_top_level_or_nested_field_invalidates_public_contract(
    tmp_path: Path,
) -> None:
    top = _perfect()
    top["private_evidence"] = True
    top_reward, _ = _grade(tmp_path / "top", top)

    nested = _perfect()
    entries = nested["entries"]
    assert isinstance(entries, list) and isinstance(entries[0], dict)
    entries[0]["timekeeper"] = "Marcus Liang"
    nested_reward, _ = _grade(tmp_path / "nested", nested)

    unsupported = _perfect()
    days = unsupported["unsupported_days"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    days[0]["supporting_message_ids"] = []
    unsupported_reward, _ = _grade(tmp_path / "unsupported", unsupported)

    support = _perfect()
    audit = support["support_audit"]
    assert isinstance(audit, list) and isinstance(audit[0], dict)
    audit[0]["reviewer"] = "Carl Jensen"
    support_reward, _ = _grade(tmp_path / "support", support)

    assert (
        top_reward
        == nested_reward
        == unsupported_reward
        == support_reward
        == {
            "answer": 0.0,
            "process": 0.0,
        }
    )


def test_dangling_agent_symlink_that_resolves_under_verifier_is_rejected(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    simulated_verifier_truth = (
        tmp_path / "verifier-mount" / "tests" / "ground_truth.json"
    )
    deliverable = workspace / "dispute.json"
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
        "numeric_cutoff_date",
        "numeric_string_total",
        "boolean_entry_count",
        "string_entry_id",
        "numeric_entry_date",
        "boolean_entry_minutes",
        "string_timekeeper_minutes",
        "numeric_timekeeper",
        "numeric_challenger",
        "numeric_challenge_date",
        "numeric_unsupported_date",
        "string_unsupported_entry_id",
        "boolean_unsupported_entry_count",
        "string_unsupported_minutes",
        "string_unsupported_billed_cents",
        "numeric_support_date",
        "string_support_entry_id",
        "numeric_gmail_id",
        "numeric_slack_ts",
        "integer_supported",
    ],
)
def test_type_invalid_public_contract_scores_zero(
    tmp_path: Path, mutation: str
) -> None:
    answer = _perfect()
    entries = answer["entries"]
    days = answer["unsupported_days"]
    audit = answer["support_audit"]
    assert isinstance(entries, list) and isinstance(entries[0], dict)
    assert isinstance(days, list) and isinstance(days[0], dict)
    assert isinstance(audit, list) and isinstance(audit[0], dict)
    if mutation == "numeric_cutoff_date":
        answer["cutoff_date"] = 20260403
    elif mutation == "numeric_string_total":
        answer["total_minutes"] = str(answer["total_minutes"])
    elif mutation == "boolean_entry_count":
        answer["entry_count"] = True
    elif mutation == "string_entry_id":
        entries[0]["id"] = str(entries[0]["id"])
    elif mutation == "numeric_entry_date":
        entries[0]["date"] = 20260406
    elif mutation == "boolean_entry_minutes":
        entries[0]["minutes"] = True
    elif mutation == "string_timekeeper_minutes":
        mapping = answer["minutes_by_timekeeper"]
        assert isinstance(mapping, dict)
        first_key = next(iter(mapping))
        mapping[first_key] = str(mapping[first_key])
    elif mutation == "numeric_timekeeper":
        timekeepers = answer["timekeepers"]
        assert isinstance(timekeepers, list)
        timekeepers[0] = 1
    elif mutation == "numeric_challenger":
        answer["challenged_by"] = 1
    elif mutation == "numeric_challenge_date":
        answer["challenge_date"] = 20260508
    elif mutation == "numeric_unsupported_date":
        days[0]["date"] = 20260404
    elif mutation == "string_unsupported_entry_id":
        days[0]["entry_ids"][0] = str(days[0]["entry_ids"][0])
    elif mutation == "boolean_unsupported_entry_count":
        days[0]["entry_count"] = False
    elif mutation == "string_unsupported_minutes":
        days[0]["minutes"] = str(days[0]["minutes"])
    elif mutation == "string_unsupported_billed_cents":
        days[0]["billed_cents"] = str(days[0]["billed_cents"])
    elif mutation == "numeric_support_date":
        audit[0]["date"] = 20260404
    elif mutation == "string_support_entry_id":
        audit[0]["entry_ids"][0] = str(audit[0]["entry_ids"][0])
    elif mutation == "numeric_gmail_id":
        email_day = next(day for day in audit if day["gmail_message_ids"])
        email_day["gmail_message_ids"][0] = 1
    elif mutation == "numeric_slack_ts":
        slack_day = next(day for day in audit if day["slack_message_ts"])
        slack_day["slack_message_ts"][0] = 1
    else:
        audit[0]["supported"] = 0

    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize(
    ("key", "criterion", "expected_f1"),
    [
        ("entries", "disputed_entries", 14 / 15),
        ("unsupported_days", "unsupported_days", 10 / 11),
        ("support_audit", "support_audit", 44 / 45),
    ],
)
def test_duplicate_outer_record_is_counted_as_an_extra(
    tmp_path: Path, key: str, criterion: str, expected_f1: float
) -> None:
    answer = _perfect()
    records = answer[key]
    assert isinstance(records, list)
    records.append(deepcopy(records[0]))

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, f"{criterion}.f1") == pytest.approx(
        expected_f1, abs=1e-4
    )
    assert _criterion(details, f"{criterion}.certified") == 0.0
    assert 0.0 < reward["answer"] < 1.0


def test_duplicate_nested_unsupported_entry_id_loses_f1_and_certification(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    days = answer["unsupported_days"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    entry_ids = days[0]["entry_ids"]
    assert isinstance(entry_ids, list)
    entry_ids.append(entry_ids[0])

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "unsupported_days.f1") == pytest.approx(0.8)
    assert _criterion(details, "unsupported_days.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.8 + 0.20 * 0.9 * 0.8, abs=1e-4)


@pytest.mark.parametrize("extra_name", ["Marcus Liang", "Avery Fake"])
def test_duplicate_or_fake_timekeeper_is_a_precision_error(
    tmp_path: Path, extra_name: str
) -> None:
    answer = _perfect()
    timekeepers = answer["timekeepers"]
    assert isinstance(timekeepers, list)
    timekeepers.append(extra_name)

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "timekeepers.f1") == pytest.approx(0.8)
    assert _criterion(details, "timekeepers.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.99 + 0.01 * 0.9 * 0.8, abs=1e-4)


@pytest.mark.parametrize(
    ("extra_name", "minutes"),
    [("Liang, Marcus", 675), ("Avery Fake", 675)],
)
def test_duplicate_alias_or_fake_timekeeper_map_key_is_a_precision_error(
    tmp_path: Path, extra_name: str, minutes: int
) -> None:
    answer = _perfect()
    mapping = answer["minutes_by_timekeeper"]
    assert isinstance(mapping, dict)
    mapping[extra_name] = minutes

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "minutes_by_timekeeper.f1") == pytest.approx(0.8)
    assert _criterion(details, "minutes_by_timekeeper.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.97 + 0.03 * 0.9 * 0.8, abs=1e-4)


def test_wrong_timekeeper_map_value_is_both_a_miss_and_an_extra(tmp_path: Path) -> None:
    answer = _perfect()
    mapping = answer["minutes_by_timekeeper"]
    assert isinstance(mapping, dict)
    mapping["Marcus Liang"] = 674

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "minutes_by_timekeeper.f1") == pytest.approx(0.5)
    assert _criterion(details, "minutes_by_timekeeper.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.97 + 0.03 * 0.9 * 0.5, abs=1e-4)


@pytest.mark.parametrize(
    ("key", "criterion", "fixed_weight", "field_weight"),
    [
        ("timekeepers", "timekeepers", 0.99, 0.01),
        (
            "minutes_by_timekeeper",
            "minutes_by_timekeeper",
            0.97,
            0.03,
        ),
    ],
)
def test_missing_timekeeper_uses_marker_aware_partial_credit(
    tmp_path: Path,
    key: str,
    criterion: str,
    fixed_weight: float,
    field_weight: float,
) -> None:
    answer = _perfect()
    value = answer[key]
    if isinstance(value, list):
        value.pop()
    else:
        assert isinstance(value, dict)
        value.pop("Peter Novak")

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, f"{criterion}.f1") == pytest.approx(2 / 3, abs=1e-4)
    assert _criterion(details, f"{criterion}.certified") == 0.0
    assert reward["answer"] == pytest.approx(
        fixed_weight + field_weight * 0.9 * (2 / 3), abs=1e-4
    )


def test_timekeeper_aliases_and_reordering_remain_exact(tmp_path: Path) -> None:
    answer = _perfect()
    answer["timekeepers"] = ["Novak, Peter", "Liang, Marcus"]
    answer["minutes_by_timekeeper"] = {
        "Novak, Peter": 215,
        "Liang, Marcus": 675,
    }

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "timekeepers.f1") == 1.0
    assert _criterion(details, "timekeepers.certified") == 1.0
    assert _criterion(details, "minutes_by_timekeeper.f1") == 1.0
    assert _criterion(details, "minutes_by_timekeeper.certified") == 1.0
    assert reward == {"answer": 1.0, "process": 0.0}


def test_reordering_sets_and_nested_members_keeps_full_credit(tmp_path: Path) -> None:
    answer = _perfect()
    entries = answer["entries"]
    timekeepers = answer["timekeepers"]
    days = answer["unsupported_days"]
    audit = answer["support_audit"]
    assert isinstance(entries, list)
    assert isinstance(timekeepers, list)
    assert isinstance(days, list)
    assert isinstance(audit, list)
    entries.reverse()
    timekeepers.reverse()
    days.reverse()
    audit.reverse()
    for day in days:
        assert isinstance(day, dict)
        entry_ids = day["entry_ids"]
        assert isinstance(entry_ids, list)
        entry_ids.reverse()
    for day in audit:
        assert isinstance(day, dict)
        for key in ("entry_ids", "gmail_message_ids", "slack_message_ts"):
            values = day[key]
            assert isinstance(values, list)
            values.reverse()

    reward, _ = _grade(tmp_path, answer)
    assert reward == {"answer": 1.0, "process": 0.0}


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, None)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_near_miss_preserves_weights_and_uses_ninety_ten_set_scoring(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["unsupported_days"] = answer["unsupported_days"][:-1]
    answer["entries"] = answer["entries"][:-1]
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "unsupported_days.f1") == pytest.approx(8 / 9, abs=1e-4)
    assert _criterion(details, "unsupported_days.certified") == 0.0
    assert _criterion(details, "disputed_entries.f1") == pytest.approx(
        12 / 13, abs=1e-4
    )
    assert _criterion(details, "disputed_entries.certified") == 0.0
    assert reward["answer"] == pytest.approx(
        0.72 + 0.20 * 0.9 * (8 / 9) + 0.08 * 0.9 * (12 / 13),
        abs=1e-4,
    )


def test_shotgun_days_score_below_a_near_miss(tmp_path: Path) -> None:
    answer = _perfect()
    answer["unsupported_days"].extend(
        {
            "date": f"2026-05-{index:02d}",
            "entry_ids": [3000 + index],
            "entry_count": 1,
            "minutes": index,
            "billed_cents": index,
        }
        for index in range(1, 31)
    )
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "unsupported_days.f1") == pytest.approx(0.25)
    assert _criterion(details, "unsupported_days.certified") == 0.0
    assert 0.84 < reward["answer"] < 0.85


def test_headline_and_exception_view_without_complete_workpaper_stays_below_half(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["support_audit"] = []

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "support_audit.f1") == 0.0
    assert _criterion(details, "support_audit.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.46)


def test_duplicate_support_identity_is_a_partial_precision_and_recall_error(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    audit = answer["support_audit"]
    assert isinstance(audit, list)
    supported_day = next(day for day in audit if day["slack_message_ts"])
    supported_day["slack_message_ts"].append(supported_day["slack_message_ts"][0])

    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "support_audit.f1") == pytest.approx(21 / 22, abs=1e-4)
    assert _criterion(details, "support_audit.certified") == 0.0
    assert 0.92 < reward["answer"] < 0.93


@pytest.mark.parametrize("contents", ["{not json", "[]", '"answer"'])
def test_malformed_deliverable_scores_zero(tmp_path: Path, contents: str) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "dispute.json").write_text(contents)
    output = tmp_path / "logs" / "reward-raw.json"
    output.parent.mkdir(parents=True)
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(output.read_text()) == {"answer": 0.0, "process": 0.0}


def test_oversized_integer_deliverable_scores_zero_without_crashing(
    tmp_path: Path,
) -> None:
    contents = '{"total_minutes": ' + "9" * 5000 + "}"
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True)
    (workspace / "dispute.json").write_text(contents)
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
def test_nonfinite_numeric_deliverable_scores_zero(
    tmp_path: Path, nonfinite: float
) -> None:
    answer = _perfect()
    answer["total_minutes"] = nonfinite
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
    return {c["name"]: c["value"] for c in details["process"]["criteria"]}


@pytest.mark.parametrize(
    ("name", "call", "ours", "builtin"),
    [
        ("native", NATIVE_CALL, 1.0, 1.0),
        ("unified", UNIFIED_CALL, 1.0, 0.0),
        ("silent", SILENT_CALL, 0.0, 0.0),
        ("mention", MENTION_CALL, 0.0, 0.0),
    ],
)
def test_tool_invoked_reads_native_and_unified_exec_trajectories(
    tmp_path: Path, name: str, call: JsonObject, ours: float, builtin: float
) -> None:
    trajectory = _trajectory(
        tmp_path, name, [{"source": "agent", "tool_calls": [call]}]
    )
    scores = _process_only(tmp_path, trajectory)
    assert scores["ours"] == ours
    assert scores["builtin"] == builtin
