"""Task-level verification: solve.sh earns full reward, the last-notice
assumption baseline earns strictly less, and the grader is deterministic.

Needs the built environment bundle (data, local-only):
    uv run python datasets/hartwell/build_tasks.py
"""

import json
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"

pytestmark = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def test_harbor_rewardkit_layout_replaces_legacy_grader() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["metadata"]["reference_tool_path_calls"] == 40
    assert "harness" not in config
    assert {
        path.name
        for path in (TASK / "tests").iterdir()
        if path.is_dir() and path.name != "__pycache__"
    } == {"answer", "process"}
    assert not (TASK / "tests" / "grade.py").exists()
    assert config["metadata"]["agent_data_scope"].startswith("Intentionally seatless")
    assert config["environment"]["docker_image"] == "workbench:dev"
    assert (
        config["environment"]["healthcheck"]["command"]
        == "sh /home/agent/workspace/.workbench/install.sh"
    )
    assert config["environment"]["mcp_servers"] == [
        {
            "name": name,
            "transport": "stdio",
            "command": f"/usr/local/bin/workbench-mcp-{name}",
        }
        for name in ("gmail", "slack", "imanage", "clio")
    ]
    assert config["agent"]["user"] == "agent"
    assert config["verifier"] == {
        "user": "verifier",
        "timeout_sec": 900.0,
        "network_mode": "no-network",
    }


def run_grader(tmp_path: Path, produce: Path) -> dict[str, float]:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    subprocess.run(
        ["sh", str(produce)],
        cwd=workspace,
        check=True,
        capture_output=True,
        env={
            "WORKBENCH_STATE": str(bundle / "state"),
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        },
    )
    logs = tmp_path / "logs"
    output = logs / "reward-raw.json"
    logs.mkdir(parents=True)
    subprocess.run(
        [
            "rewardkit",
            str(TASK / "tests"),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(output.read_text())


def test_solve_python_emits_json_without_writing_workspace(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=workspace,
        env={
            "WORKBENCH_STATE": str(bundle / "state"),
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        },
        check=True,
        capture_output=True,
        text=True,
    )

    assert isinstance(json.loads(completed.stdout), dict)
    assert completed.stderr == ""
    assert not (workspace / "deadline.json").exists()


def test_solution_earns_full_reward(tmp_path: Path) -> None:
    reward = run_grader(tmp_path, TASK / "solution" / "solve.sh")
    assert reward == {"answer": 1.0, "process": 0.0}


def test_naive_baseline_earns_strictly_less(tmp_path: Path) -> None:
    solved = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive = run_grader(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["answer"] < solved["answer"] - 0.4, (
        f"the Slack correction must discriminate: naive={naive['answer']}"
    )
    assert naive["answer"] > 0.1


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    empty = tmp_path / "noop.sh"
    empty.write_text("true\n")
    reward = run_grader(tmp_path, empty)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_grading_is_deterministic(tmp_path: Path) -> None:
    first = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    second = run_grader(tmp_path / "b", TASK / "solution" / "solve.sh")
    assert first == second


def test_instruction_states_the_rule_without_naming_the_decoy() -> None:
    """The agent must apply the scoping rule, not be handed the exception.

    Nine of nine measured cells partitioned the stale references exactly.
    The instruction used to warn that another matter moved that season,
    which turns "find the contaminated messages" into "check the ones I
    was told about". The rule that resolves it stays, so the answer is
    still fully derivable.

    Phrases are matched against whitespace-normalized text: the source is
    hard-wrapped, so a raw substring check would pass for the wrong
    reason on any phrase that happens to straddle a line break.
    """

    instruction = " ".join((TASK / "instruction.md").read_text().split())

    assert "as this hearing's setting" in instruction
    assert "Cross-reference every mention of every noticed date" in instruction
    assert "a different case's hearing date is not this hearing's" not in instruction
