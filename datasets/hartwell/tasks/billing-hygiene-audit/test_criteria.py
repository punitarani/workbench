"""Synthetic contract tests for the billing hygiene Reward Kit verifier."""

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
    return json.loads((TESTS / "ground_truth.json").read_text())


def _perfect() -> JsonObject:
    truth = _truth()
    return {
        "entries_reviewed": truth["entries_reviewed"],
        "timekeepers_reviewed": truth["timekeepers_reviewed"],
        "anomalous_timekeeper_days": deepcopy(truth["anomalous_timekeeper_days"]),
        "anomalous_entry_count": truth["anomalous_entry_count"],
        "anomalous_minutes_total": truth["anomalous_minutes_total"],
        "anomalous_billed_cents_total": truth["anomalous_billed_cents_total"],
        "phantom_note_ids": deepcopy(truth["phantom_note_ids"]),
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
def test_extra_top_level_field_forfeits_full_answer_credit(
    tmp_path: Path, extra_key: str, extra_value: object
) -> None:
    answer = _perfect()
    answer[extra_key] = extra_value
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "deliverable_format") == 0.0
    assert reward == {"answer": 0.91, "process": 0.0}


def test_extra_anomalous_day_key_forfeits_full_answer_credit(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    days = answer["anomalous_timekeeper_days"]
    assert isinstance(days, list) and isinstance(days[0], dict)
    days[0]["unsupported_entries"] = []
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "deliverable_format") == 0.0
    assert reward == {"answer": 0.91, "process": 0.0}


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, None)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_near_miss_uses_ninety_ten_scoring_for_anomalous_days(
    tmp_path: Path,
) -> None:
    answer = _perfect()
    answer["anomalous_timekeeper_days"] = answer["anomalous_timekeeper_days"][:-1]
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "anomalous_days.f1") == pytest.approx(0.8)
    assert _criterion(details, "answer", "anomalous_days.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.34 + 0.66 * 0.9 * 0.8, abs=1e-4)


def test_phantom_note_set_also_uses_ninety_ten_scoring(tmp_path: Path) -> None:
    answer = _perfect()
    answer["phantom_note_ids"] = [176, 999]
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "phantom_notes.f1") == pytest.approx(
        2 / 3, abs=1e-4
    )
    assert _criterion(details, "answer", "phantom_notes.certified") == 0.0
    assert reward["answer"] == pytest.approx(0.9 + 0.1 * 0.9 * (2 / 3), abs=1e-4)


def test_shotgun_days_score_below_a_near_miss(tmp_path: Path) -> None:
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
    assert 0.4 < reward["answer"] < 0.5


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
