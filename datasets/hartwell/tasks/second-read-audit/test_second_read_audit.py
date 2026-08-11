"""Task-level verification: solve.sh earns full reward, the same-day
baseline earns strictly less, and the grader is deterministic.

Needs the built environment bundle (data, local-only):
    uv run python datasets/hartwell/build_tasks.py
"""

import json
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
EPOCH = date(2026, 3, 2)
REQUEST = "mind taking a quick look at my draft before it goes out?"
PACIFIC = ZoneInfo("America/Los_Angeles")

pytestmark = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def test_harbor_rewardkit_layout_replaces_legacy_grader() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["metadata"]["reference_tool_path_calls"] == 54
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


def _rows(database: str, sql: str) -> list[tuple]:
    with sqlite3.connect(BUNDLE / "state" / database) as connection:
        return connection.execute(sql).fetchall()


def _day(timestamp: int) -> date:
    return EPOCH + timedelta(days=timestamp // 86_400)


def _iso(timestamp: int) -> str:
    return (
        datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=timestamp)
    ).isoformat()


def _next_working_day(value: date) -> date:
    value += timedelta(days=1)
    while value.weekday() >= 5:
        value += timedelta(days=1)
    return value


def test_reference_response_audit_matches_fresh_bundle() -> None:
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
    names = dict(_rows("slack.db", "SELECT person_id, name FROM people"))
    members: dict[str, set[str]] = {}
    for conversation_id, person_id in _rows(
        "slack.db", "SELECT conversation_id, person_id FROM members"
    ):
        members.setdefault(conversation_id, set()).add(person_id)
    dm_ids = {
        conversation_id
        for (conversation_id,) in _rows(
            "slack.db", "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
        )
    }
    messages: dict[str, list[tuple[str, str, int, str]]] = {}
    for conversation_id, sender, body, timestamp, timestamp_id in _rows(
        "slack.db",
        "SELECT conversation_id, sender, body, time, ts FROM messages ORDER BY time",
    ):
        if conversation_id in dm_ids:
            messages.setdefault(conversation_id, []).append(
                (sender, body, timestamp, timestamp_id)
            )
    recipients: dict[str, set[str]] = {}
    for message_id, person_id in _rows(
        "gmail.db", "SELECT message_id, person_id FROM recipients"
    ):
        recipients.setdefault(message_id, set()).add(person_id)
    mail = [
        (sender, recipient, timestamp, message_id)
        for message_id, sender, timestamp in _rows(
            "gmail.db", "SELECT message_id, sender, time FROM messages"
        )
        for recipient in recipients.get(message_id, ())
    ]

    expected = []
    for conversation_id, lane in messages.items():
        for position, (sender, body, asked_at, request_ts) in enumerate(lane):
            if body.strip().lower() != REQUEST:
                continue
            (asked_of,) = members[conversation_id] - {sender}
            candidates = [
                (timestamp, "slack", timestamp_id)
                for reply_sender, _, timestamp, timestamp_id in lane[position + 1 :]
                if reply_sender == asked_of and timestamp > asked_at
            ]
            candidates.extend(
                (timestamp, "gmail", message_id)
                for mail_sender, recipient, timestamp, message_id in mail
                if mail_sender == asked_of
                and recipient == sender
                and timestamp > asked_at
            )
            first = min(candidates, default=None)
            asked_on = _day(asked_at)
            deadline = _next_working_day(asked_on)
            if first is None:
                outcome = "unanswered"
            elif _day(first[0]) == asked_on:
                outcome = "same_day"
            elif _day(first[0]) <= deadline:
                outcome = "next_working_day"
            else:
                outcome = "unanswered"
            expected.append(
                {
                    "request_ts": request_ts,
                    "request_date": asked_on.isoformat(),
                    "asked_by": names[sender],
                    "asked_of": names[asked_of],
                    "first_response_surface": first[1] if first else "none",
                    "first_response_id": first[2] if first else "",
                    "first_response_at": _iso(first[0]) if first else "",
                    "outcome": outcome,
                }
            )
    expected.sort(key=lambda row: float(row["request_ts"]))
    outcomes = Counter(row["outcome"] for row in expected)
    surfaces = Counter(row["first_response_surface"] for row in expected)

    assert len(expected) == 75
    assert outcomes == {"same_day": 67, "next_working_day": 5, "unanswered": 3}
    assert surfaces == {"slack": 74, "gmail": 1}
    assert answer["response_audit"] == expected
    assert answer["requests_reviewed"] == 75
    assert answer["answered_same_day"] == 67
    assert answer["answered_next_working_day"] == 5
    assert answer["unanswered_by_deadline"] == 3


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
    assert not (workspace / "second-read.json").exists()


def test_solution_earns_full_reward(tmp_path: Path) -> None:
    reward = run_grader(tmp_path, TASK / "solution" / "solve.sh")
    assert reward == {"answer": 1.0, "process": 0.0}


def test_naive_baseline_earns_strictly_less(tmp_path: Path) -> None:
    solved = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive = run_grader(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["answer"] < solved["answer"] - 0.4, (
        f"the window and the mail surface must discriminate: naive={naive['answer']}"
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
