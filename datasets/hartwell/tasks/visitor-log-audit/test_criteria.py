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
    return json.loads((TESTS / "ground_truth.json").read_text())


def _perfect() -> JsonObject:
    truth = _truth()
    return {
        "requests_reviewed": truth["requests_reviewed"],
        "conversations_reviewed": truth["conversations_reviewed"],
        "same_day_breach_ts": deepcopy(truth["same_day_breach_ts"]),
        "same_day_breaches": deepcopy(truth["same_day_breaches"]),
        "returned_same_day": truth["returned_same_day"],
        "returned_next_working_day_ts": deepcopy(truth["returned_next_working_day_ts"]),
        "unresolved_ts": deepcopy(truth["unresolved_ts"]),
    }


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


def test_extra_top_level_or_nested_field_forfeits_format_credit(
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
    assert top_reward == nested_reward == {"answer": 0.91, "process": 0.0}


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


def test_reordering_all_sets_keeps_full_credit(tmp_path: Path) -> None:
    answer = _perfect()
    for key in (
        "same_day_breach_ts",
        "same_day_breaches",
        "returned_next_working_day_ts",
        "unresolved_ts",
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


def test_shotgun_breaches_score_below_a_near_miss(tmp_path: Path) -> None:
    answer = _perfect()
    for index in range(200):
        ts = f"99{index:04d}.999999"
        answer["same_day_breach_ts"].append(ts)
        answer["same_day_breaches"].append(
            {
                "ts": ts,
                "date": "2026-07-01",
                "asked_by": f"Decoy {index}",
                "asked_of": "Nobody",
                "resolution": "unresolved",
            }
        )
    reward, details = _grade(tmp_path, answer)

    assert _criterion(details, "answer", "breach_ts.f1") == pytest.approx(
        24 / 224, abs=1e-4
    )
    assert _criterion(details, "answer", "breaches.f1") == pytest.approx(
        24 / 224, abs=1e-4
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
