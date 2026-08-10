"""Bundle-backed tests for the fee-dispute reconstruction task."""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
TRUTH = json.loads((TESTS / "ground_truth.json").read_text())

pytestmark = [
    pytest.mark.skipif(
        REWARDKIT is None,
        reason="rewardkit not on PATH; uv tool install harbor-rewardkit[all]==0.1.7",
    ),
    pytest.mark.skipif(
        not BUNDLE.exists(),
        reason="task bundle not built; run datasets/hartwell/build_tasks.py",
    ),
]


def _score(workspace: Path, out_dir: Path) -> tuple[dict, dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    output = out_dir / "reward-raw.json"
    subprocess.run(
        [REWARDKIT, str(TESTS), "--workspace", str(workspace), "--output", str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        json.loads(output.read_text()),
        json.loads((out_dir / "reward-details.json").read_text()),
    )


def _criterion(details: dict, name: str) -> float:
    for score in details["answer"]["criteria"]:
        if score["name"] == name:
            return score["value"]
    raise AssertionError(f"no criterion {name!r} in answer")


def _produce(tmp_path: Path, script: Path | None) -> Path:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    if script is not None:
        subprocess.run(
            ["bash", str(script)],
            cwd=workspace,
            check=True,
            capture_output=True,
            env={
                "WORKBENCH_STATE": str(bundle / "state"),
                "WORKBENCH_WORKSPACE": str(workspace),
                "PATH": f"/usr/bin:/bin:{Path(sys.executable).parent}",
            },
        )
    return workspace


def _graded(tmp_path: Path, script: Path | None) -> tuple[Path, dict, dict]:
    workspace = _produce(tmp_path, script)
    reward, details = _score(workspace, tmp_path / "logs")
    return workspace, reward, details


def _verified(workspace: Path, out_dir: Path) -> tuple[dict, dict, dict]:
    env = dict(os.environ)
    env.update(
        {
            "VERIFIER_LOG_DIR": str(out_dir),
            "WORKBENCH_WORKSPACE": str(workspace),
        }
    )
    subprocess.run(
        ["sh", str(TESTS / "test.sh")],
        cwd=workspace,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    return (
        json.loads((out_dir / "reward.json").read_text()),
        json.loads((out_dir / "reward-raw.json").read_text()),
        json.loads((out_dir / "reward-details.json").read_text()),
    )


def test_oracle_earns_canonical_reward_with_zero_process(tmp_path: Path) -> None:
    workspace = _produce(tmp_path, TASK / "solution" / "solve.sh")
    combined, raw, details = _verified(workspace, tmp_path / "logs")

    assert raw == {"answer": 1.0, "process": 0.0}
    assert combined == {"reward": 1.0, "answer": 1.0, "process": 0.0}
    assert set(details) == {"answer", "process"}


def test_naive_baseline_earns_strictly_less_answer_credit(tmp_path: Path) -> None:
    _, solved, _ = _graded(tmp_path / "a", TASK / "solution" / "solve.sh")
    _, naive, _ = _graded(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["answer"] < solved["answer"] - 0.2, naive
    assert naive["answer"] > 0.1, naive


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    _, reward, _ = _graded(tmp_path, None)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_grading_is_deterministic(tmp_path: Path) -> None:
    _, first, _ = _graded(tmp_path / "a", TASK / "solution" / "solve.sh")
    _, second, _ = _graded(tmp_path / "b", TASK / "solution" / "solve.sh")
    assert first == second


def test_one_missing_day_and_entry_receive_f1_partial_credit(tmp_path: Path) -> None:
    workspace = _produce(tmp_path, TASK / "solution" / "solve.sh")
    deliverable = workspace / "dispute.json"
    answer = json.loads(deliverable.read_text())
    answer["unsupported_days"] = answer["unsupported_days"][:-1]
    answer["entries"] = answer["entries"][:-1]
    deliverable.write_text(json.dumps(answer, indent=2))

    reward, details = _score(workspace, tmp_path / "logs")
    assert _criterion(details, "unsupported_days.f1") == pytest.approx(8 / 9, abs=1e-4)
    assert _criterion(details, "unsupported_days.certified") == 0.0
    assert _criterion(details, "disputed_entries.f1") == pytest.approx(
        12 / 13, abs=1e-4
    )
    assert _criterion(details, "disputed_entries.certified") == 0.0
    assert 0.8 < reward["answer"] < 0.9


def test_ground_truth_and_oracle_match_the_fresh_bundle(tmp_path: Path) -> None:
    workspace = _produce(tmp_path, TASK / "solution" / "solve.sh")
    answer = json.loads((workspace / "dispute.json").read_text())

    assert "unsupported_entry_ids" not in answer
    assert answer["cutoff_date"] == TRUTH["cutoff_date"] == "2026-04-03"
    assert answer["total_minutes"] == TRUTH["total_minutes"] == 890
    assert answer["entry_count"] == TRUTH["entry_count"] == 7
    assert [entry["id"] for entry in answer["entries"]] == [
        1374,
        1378,
        1481,
        1575,
        1577,
        1666,
        1756,
    ]
    assert answer["entries"] == TRUTH["entries"]
    assert answer["unsupported_days"] == TRUTH["unsupported_days"]
    assert answer["challenge_date"] == TRUTH["challenge_date"] == "2026-05-08"


def test_unsupported_day_invariants_are_explicit() -> None:
    days = TRUTH["unsupported_days"]
    ids = [entry_id for day in days for entry_id in day["entry_ids"]]

    assert len(days) == 5
    assert sum(day["entry_count"] for day in days) == 47
    assert len(ids) == len(set(ids)) == 47
    assert all(day["entry_count"] == len(day["entry_ids"]) for day in days)
    assert [day["billed_cents"] for day in days] == [
        195400,
        492400,
        565750,
        715142,
        89000,
    ]
    assert sum(day["minutes"] for day in days) == 2887
    assert sum(day["billed_cents"] for day in days) == 2057692
