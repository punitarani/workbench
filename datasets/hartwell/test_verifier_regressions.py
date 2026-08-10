"""Cross-task regressions for the Hartwell verifier boundary."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

HARTWELL = Path(__file__).parent
TASKS = HARTWELL / "tasks"
REWARDKIT = shutil.which("rewardkit")

type TaskCase = tuple[str, str, str, str]

CASES: tuple[TaskCase, ...] = (
    (
        "billing-hygiene-audit",
        "hygiene.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "client-departure-postmortem",
        "postmortem.json",
        "search_threads",
        "gmail__search_threads",
    ),
    (
        "fee-dispute-reconstruction",
        "dispute.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "operative-deadline",
        "deadline.json",
        "slack_search_public_and_private",
        "slack__slack_search_public_and_private",
    ),
    (
        "second-read-audit",
        "second-read.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
    (
        "standard-drift",
        "drift.json",
        "get_document_versions",
        "imanage__get_document_versions",
    ),
    (
        "vanished-clause",
        "vanished.json",
        "get_document_versions",
        "imanage__get_document_versions",
    ),
    (
        "visitor-log-audit",
        "visitor-log.json",
        "slack_read_channel",
        "slack__slack_read_channel",
    ),
)

pytestmark = pytest.mark.skipif(REWARDKIT is None, reason="rewardkit not installed")


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_deeply_nested_deliverable_is_malformed_zero(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    del tool, native
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    pathological = '{"nested":' + "[" * 2_000 + "0" + "]" * 2_000 + "}"
    (workspace / deliverable).write_text(pathological)
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(TASKS / task / "tests"),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(output.read_text()) == {"answer": 0.0, "process": 0.0}


@pytest.mark.parametrize(("task", "deliverable", "tool", "native"), CASES)
def test_tool_invoked_requires_executable_unified_expression(
    tmp_path: Path, task: str, deliverable: str, tool: str, native: str
) -> None:
    del deliverable
    source = f"await tools.{native}({{}})"
    trajectories = {
        "native": {"function_name": native},
        "unified": {
            "function_name": "exec",
            "arguments": {"input": f"const result = {source};"},
        },
        "line_comment": {
            "function_name": "exec",
            "arguments": {"input": f"// {source}\ntext('done');"},
        },
        "block_comment": {
            "function_name": "exec",
            "arguments": {"input": f"/* {source} */\ntext('done');"},
        },
        "string": {
            "function_name": "exec",
            "arguments": {"input": f'const hint = "{source}"; text(hint);'},
        },
    }
    paths: dict[str, Path] = {}
    for name, call in trajectories.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps({"steps": [{"tool_calls": [call]}]}))
        paths[name] = path

    tests = tmp_path / "tests"
    (tests / "process").mkdir(parents=True)
    shutil.copyfile(TASKS / task / "tests" / "criteria.py", tests / "criteria.py")
    registrations = ["import rewardkit as rk"]
    registrations.extend(
        f"rk.tool_invoked({tool!r}, path={str(path)!r}, name={name!r})"
        for name, path in paths.items()
    )
    (tests / "process" / "method.py").write_text("\n".join(registrations) + "\n")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    output = tmp_path / "reward.json"

    completed = subprocess.run(
        [
            REWARDKIT,
            str(tests),
            "--workspace",
            str(workspace),
            "--output",
            str(output),
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0, completed.stderr
    details = json.loads((tmp_path / "reward-details.json").read_text())
    scores = {
        criterion["name"]: criterion["value"]
        for criterion in details["process"]["criteria"]
    }
    assert scores == {
        "native": 1.0,
        "unified": 1.0,
        "line_comment": 0.0,
        "block_comment": 0.0,
        "string": 0.0,
    }
