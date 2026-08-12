"""Task-level verification: solve.sh earns full reward, the email-trail
assumption baseline earns strictly less, and the grader is deterministic.

Needs the built environment bundle (data, local-only):
    uv run python datasets/hartwell/build_tasks.py
"""

import importlib.util
import json
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from datetime import date, timedelta
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
EPOCH = date(2026, 3, 2)

needs_bundle = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def test_harbor_rewardkit_layout_replaces_legacy_grader() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["metadata"]["reference_tool_path_calls"] == 199
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


def test_document_mention_markers_match_storyline_registry() -> None:
    from workbench.workplaces.hartwell.storylines import DOC_MENTION_MARKERS

    solution_path = TASK / "solution" / "solve.py"
    spec = importlib.util.spec_from_file_location(
        "vanished_clause_solution", solution_path
    )
    assert spec is not None and spec.loader is not None
    solution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(solution)

    assert solution.DOC_MENTION_MARKERS == DOC_MENTION_MARKERS


def _rows(database: str, sql: str) -> list[tuple]:
    with sqlite3.connect(BUNDLE / "state" / database) as connection:
        return connection.execute(sql).fetchall()


def _day(timestamp: int) -> str:
    return (EPOCH + timedelta(days=timestamp // 86400)).isoformat()


@needs_bundle
def test_reference_revision_ledger_matches_fresh_bundle() -> None:
    from workbench.workplaces.hartwell.storylines import DOC_MENTION_MARKERS

    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=BUNDLE / "workspace",
        env={
            "WORKBENCH_STATE": str(BUNDLE / "state"),
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    answer = json.loads(completed.stdout)
    documents = {
        document_id: (name, path, number)
        for document_id, name, path, number in _rows(
            "imanage.db",
            "SELECT document_id, name, path, document_number FROM documents",
        )
    }
    versions = _rows(
        "imanage.db",
        "SELECT document_id, version, time FROM versions ORDER BY document_id, version",
    )
    post_v1 = [row for row in versions if row[1] > 1]

    attachment_text: dict[str, str] = {}
    for message_id, filename in _rows(
        "gmail.db", "SELECT message_id, filename FROM attachments"
    ):
        attachment_text[message_id] = (
            f"{attachment_text.get(message_id, '')} {filename}".strip()
        )
    emails_by_day: dict[str, list[tuple[str, str]]] = {}
    for message_id, subject, body, timestamp in _rows(
        "gmail.db", "SELECT message_id, subject, body, time FROM messages"
    ):
        text = f"{subject} {body} {attachment_text.get(message_id, '')}".lower()
        emails_by_day.setdefault(_day(timestamp), []).append((message_id, text))
    slack_by_day: dict[str, list[tuple[str, str]]] = {}
    for timestamp_id, body, timestamp in _rows(
        "slack.db",
        "SELECT m.ts, m.body, m.time FROM messages m "
        "JOIN conversations c ON c.conversation_id = m.conversation_id "
        "WHERE c.kind != 'dm'",
    ):
        slack_by_day.setdefault(_day(timestamp), []).append(
            (timestamp_id, body.lower())
        )

    expected = []
    for document_id, version, timestamp in post_v1:
        name, path, number = documents[document_id]
        markers = DOC_MENTION_MARKERS[name]
        saved = _day(timestamp)
        email_ids = sorted(
            message_id
            for message_id, text in emails_by_day.get(saved, [])
            if any(marker in text for marker in markers)
        )
        public_slack_ts = sorted(
            timestamp_id
            for timestamp_id, text in slack_by_day.get(saved, [])
            if any(marker in text for marker in markers)
        )
        expected.append(
            {
                "version_id": f"LEGAL!{number}.{version}",
                "document_number": number,
                "document_path": path,
                "date": saved,
                "coverage_status": (
                    "covered" if email_ids or public_slack_ts else "unreviewed"
                ),
                "email_ids": email_ids,
                "public_slack_ts": public_slack_ts,
            }
        )

    assert len(expected) == 57
    assert sum(row["coverage_status"] == "covered" for row in expected) == 52
    assert sum(row["coverage_status"] == "unreviewed" for row in expected) == 5
    assert (
        sum(len(row["email_ids"]) + len(row["public_slack_ts"]) for row in expected)
        == 53
    )
    assert answer["revision_audit"] == expected
    assert answer["revisions_reviewed"] == 57
    assert answer["covered_revisions"] == 52
    assert answer["unreviewed_revision_count"] == 5
    assert answer["covering_communications"] == 53


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


@needs_bundle
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
    assert not (workspace / "clause.json").exists()


@needs_bundle
def test_solution_earns_full_reward(tmp_path: Path) -> None:
    reward = run_grader(tmp_path, TASK / "solution" / "solve.sh")
    assert reward == {"answer": 1.0, "process": 0.0}


@needs_bundle
def test_naive_baseline_earns_strictly_less(tmp_path: Path) -> None:
    solved = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive = run_grader(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["answer"] < solved["answer"] - 0.4, (
        f"the version diff must discriminate: naive={naive['answer']}"
    )
    # Was 0.1, when ledger_reconciles was vacuously true over the empty
    # ledger this baseline submits and paid it 3.0 for reconciling nothing.
    # The floor still has to sit above what a hollow file earns (0.03), so
    # that the baseline is credited for the retrieval it does do.
    assert naive["answer"] > 0.08


@needs_bundle
def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    empty = tmp_path / "noop.sh"
    empty.write_text("true\n")
    reward = run_grader(tmp_path, empty)
    assert reward == {"answer": 0.0, "process": 0.0}


@needs_bundle
def test_grading_is_deterministic(tmp_path: Path) -> None:
    first = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    second = run_grader(tmp_path / "b", TASK / "solution" / "solve.sh")
    assert first == second
