"""Synthetic contract tests for the fee reconstruction verifier."""

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

UNSUPPORTED_DAYS = [
    {
        "date": "2026-04-04",
        "entry_ids": [1316, 1317, 1318, 1319],
        "entry_count": 4,
        "minutes": 300,
        "billed_cents": 195400,
    },
    {
        "date": "2026-04-13",
        "entry_ids": [1606, 1607, 1614, 1616, 1618, 1623, 1624, 1629, 1631],
        "entry_count": 9,
        "minutes": 660,
        "billed_cents": 492400,
    },
    {
        "date": "2026-04-20",
        "entry_ids": [
            1826,
            1830,
            1836,
            1842,
            1844,
            1845,
            1848,
            1857,
            1861,
            1863,
            1865,
            1866,
            1867,
            1868,
            1872,
        ],
        "entry_count": 15,
        "minutes": 786,
        "billed_cents": 565750,
    },
    {
        "date": "2026-04-22",
        "entry_ids": [
            1930,
            1932,
            1935,
            1942,
            1950,
            1955,
            1960,
            1963,
            1964,
            1965,
            1969,
            1973,
            1974,
            1976,
            1977,
            1980,
        ],
        "entry_count": 16,
        "minutes": 1021,
        "billed_cents": 715142,
    },
    {
        "date": "2026-04-25",
        "entry_ids": [2087, 2089, 2090],
        "entry_count": 3,
        "minutes": 120,
        "billed_cents": 89000,
    },
]

pytestmark = pytest.mark.skipif(
    REWARDKIT is None,
    reason="rewardkit not on PATH; uv tool install harbor-rewardkit[all]==0.1.7",
)


def _perfect() -> dict:
    return {
        "cutoff_date": "2026-04-03",
        "total_minutes": 890,
        "entry_count": 7,
        "entries": [
            {"id": 1374, "date": "2026-04-06", "minutes": 130},
            {"id": 1378, "date": "2026-04-06", "minutes": 95},
            {"id": 1481, "date": "2026-04-08", "minutes": 145},
            {"id": 1575, "date": "2026-04-10", "minutes": 160},
            {"id": 1577, "date": "2026-04-10", "minutes": 120},
            {"id": 1666, "date": "2026-04-14", "minutes": 150},
            {"id": 1756, "date": "2026-04-16", "minutes": 90},
        ],
        "minutes_by_timekeeper": {"Marcus Liang": 675, "Peter Novak": 215},
        "timekeepers": ["Marcus Liang", "Peter Novak"],
        "challenged_by": "Priya Raman",
        "challenge_date": "2026-05-08",
        "unsupported_days": deepcopy(UNSUPPORTED_DAYS),
    }


def _grade(tmp_path: Path, answer: dict | None) -> tuple[dict, dict]:
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


def _criterion(details: dict, name: str) -> float:
    for score in details["answer"]["criteria"]:
        if score["name"] == name:
            return score["value"]
    raise AssertionError(f"no criterion {name!r} in answer")


def test_exact_answer_has_only_the_canonical_raw_dimensions(tmp_path: Path) -> None:
    reward, _ = _grade(tmp_path, _perfect())
    assert set(reward) == {"answer", "process"}
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
        0.32 + 0.56 * 0.9 * (8 / 9) + 0.12 * 0.9 * (12 / 13),
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
    assert 0.44 < reward["answer"] < 0.60


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


def _trajectory(tmp_path: Path, name: str, steps: list[dict]) -> Path:
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


def _process_only(tmp_path: Path, trajectory: Path) -> dict:
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
    ],
)
def test_tool_invoked_reads_native_and_unified_exec_trajectories(
    tmp_path: Path, name: str, call: dict, ours: float, builtin: float
) -> None:
    trajectory = _trajectory(
        tmp_path, name, [{"source": "agent", "tool_calls": [call]}]
    )
    scores = _process_only(tmp_path, trajectory)
    assert scores["ours"] == ours
    assert scores["builtin"] == builtin
