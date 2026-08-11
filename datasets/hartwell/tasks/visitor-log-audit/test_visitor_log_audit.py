"""Bundle-backed and Harbor-contract tests for visitor-log-audit."""

import importlib.util
import inspect
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
PUBLIC_FIELDS = {
    "requests_reviewed",
    "conversations_reviewed",
    "same_day_breach_ts",
    "same_day_breaches",
    "returned_same_day",
    "returned_next_working_day",
    "unresolved_by_followup",
    "returned_next_working_day_ts",
    "unresolved_ts",
    "custody_audit",
}
BREACH_FIELDS = {"ts", "date", "asked_by", "asked_of", "resolution"}

type JsonObject = dict[str, object]

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


def _truth() -> JsonObject:
    return json.loads((TESTS / "oracle.json").read_text())


def _score(workspace: Path, out_dir: Path) -> tuple[JsonObject, JsonObject]:
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


def _produce(tmp_path: Path, script: Path | None) -> Path:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    if script is not None:
        subprocess.run(
            ["sh", str(script)],
            cwd=workspace,
            check=True,
            capture_output=True,
            text=True,
            env={
                "WORKBENCH_STATE": str(bundle / "state"),
                "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
            },
        )
    return workspace


def _verified(
    workspace: Path, out_dir: Path
) -> tuple[JsonObject, JsonObject, JsonObject]:
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


def _solve_with_state(state: Path, cwd: Path) -> JsonObject:
    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=cwd,
        env={
            "WORKBENCH_STATE": str(state),
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        },
        check=True,
        capture_output=True,
        text=True,
    )
    assert completed.stderr == ""
    return json.loads(completed.stdout)


def test_rewardkit_layout_has_exactly_answer_and_process_dimensions() -> None:
    dimensions = {
        path.name
        for path in TESTS.iterdir()
        if path.is_dir() and path.name != "__pycache__"
    }
    assert dimensions == {"answer", "process"}
    assert not (TESTS / "grade.py").exists()


def test_task_uses_harbor_schema_and_secure_stdio_contract() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())

    assert config["schema_version"] == "1.3"
    assert config["task"]["name"] == "workbench/visitor-log-audit"
    assert config["metadata"]["reference_tool_path_calls"] > 0
    assert "harness" not in config
    assert set(config["environment"]) >= {
        "docker_image",
        "os",
        "workdir",
        "memory_mb",
        "network_mode",
        "allowed_hosts",
        "healthcheck",
        "mcp_servers",
    }
    assert config["environment"]["mcp_servers"] == [
        {
            "name": name,
            "transport": "stdio",
            "command": f"/usr/local/bin/workbench-mcp-{name}",
        }
        for name in ("gmail", "slack", "imanage", "clio")
    ]
    assert config["environment"]["healthcheck"]["command"] == (
        "sh /home/agent/workspace/.workbench/install.sh"
    )
    assert config["agent"]["user"] == "agent"
    assert config["verifier"] == {
        "user": "verifier",
        "timeout_sec": 900.0,
        "network_mode": "no-network",
    }


def test_instruction_defines_exact_public_and_temporal_contract() -> None:
    instruction = (TASK / "instruction.md").read_text()

    for field in PUBLIC_FIELDS | BREACH_FIELDS:
        assert field in instruction
    for phrase in (
        "end of the day it was asked",
        "after the request",
        "same DM lane",
        "directed to the asker",
        "next_working_day",
        "unresolved",
        "intentionally seatless",
    ):
        assert phrase.lower() in instruction.lower()
    assert "open_handover_ts" not in instruction
    assert "closed_next_day" not in instruction


def test_solve_module_is_importable_annotated_and_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    solve_path = TASK / "solution" / "solve.py"
    spec = importlib.util.spec_from_file_location("visitor_log_solve", solve_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.chdir(tmp_path)
    spec.loader.exec_module(module)

    assert not (tmp_path / "visitor-log.json").exists()
    functions = [
        function
        for _, function in inspect.getmembers(module, inspect.isfunction)
        if function.__module__ == module.__name__
    ]
    assert {function.__name__ for function in functions} >= {
        "build_visitor_log",
        "next_working_day",
        "main",
    }
    for function in functions:
        signature = inspect.signature(function)
        assert signature.return_annotation is not inspect.Signature.empty
        assert all(
            parameter.annotation is not inspect.Parameter.empty
            for parameter in signature.parameters.values()
        )


def test_unpacked_bundle_oracle_uses_relative_state_without_overrides(
    tmp_path: Path,
) -> None:
    workspace = _produce(tmp_path, TASK / "solution" / "solve.sh")
    assert json.loads((workspace / "visitor-log.json").read_text()) == _truth()


def test_solve_python_emits_document_without_writing_workspace(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    document = _solve_with_state(bundle / "state", workspace)

    assert document == _truth()
    assert not (workspace / "visitor-log.json").exists()


def test_oracle_earns_canonical_reward_with_zero_process(tmp_path: Path) -> None:
    workspace = _produce(tmp_path, TASK / "solution" / "solve.sh")
    combined, raw, details = _verified(workspace, tmp_path / "logs")

    assert raw == {"answer": 1.0, "process": 0.0}
    assert combined == {"reward": 1.0, "answer": 1.0, "process": 0.0}
    assert set(details) == {"answer", "process"}


def test_naive_baseline_remains_more_than_point_four_below_oracle(
    tmp_path: Path,
) -> None:
    solved_workspace = _produce(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive_workspace = _produce(tmp_path / "b", TASK / "baseline" / "naive.sh")
    solved, _ = _score(solved_workspace, tmp_path / "a" / "logs")
    naive, _ = _score(naive_workspace, tmp_path / "b" / "logs")

    assert naive["answer"] < solved["answer"] - 0.4, naive
    assert naive["answer"] > 0.1, naive


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    reward, _ = _score(_produce(tmp_path, None), tmp_path / "logs")
    assert reward == {"answer": 0.0, "process": 0.0}


def test_grading_is_deterministic(tmp_path: Path) -> None:
    first_workspace = _produce(tmp_path / "a", TASK / "solution" / "solve.sh")
    second_workspace = _produce(tmp_path / "b", TASK / "solution" / "solve.sh")
    first, _ = _score(first_workspace, tmp_path / "a" / "logs")
    second, _ = _score(second_workspace, tmp_path / "b" / "logs")
    assert first == second


def test_ground_truth_matches_fresh_bundle_invariants() -> None:
    truth = _truth()
    breaches = truth["same_day_breaches"]
    assert isinstance(breaches, list)

    assert truth["requests_reviewed"] == 71
    assert truth["conversations_reviewed"] == 12
    assert truth["returned_same_day"] == 59
    assert truth["returned_next_working_day"] == 10
    assert truth["unresolved_by_followup"] == 2
    assert len(breaches) == 12
    assert len(truth["returned_next_working_day_ts"]) == 10
    assert truth["unresolved_ts"] == ["7456314.002498", "7569818.002563"]
    assert truth["same_day_breach_ts"] == [record["ts"] for record in breaches]
    assert all(set(record) == BREACH_FIELDS for record in breaches)


def test_reference_custody_audit_matches_fresh_bundle() -> None:
    state = BUNDLE / "state"
    document = _solve_with_state(state, BUNDLE / "workspace")
    epoch = date(2026, 3, 2)
    pacific = timezone(timedelta(hours=-8))
    connection = sqlite3.connect(f"file:{state / 'slack.db'}?mode=ro", uri=True)
    connection.execute("ATTACH DATABASE ? AS gmail", (str(state / "gmail.db"),))
    names = dict(connection.execute("SELECT person_id, name FROM people"))
    members: dict[str, set[str]] = {}
    for conversation_id, person_id in connection.execute(
        "SELECT conversation_id, person_id FROM members"
    ):
        members.setdefault(conversation_id, set()).add(person_id)
    dm_ids = {
        conversation_id
        for (conversation_id,) in connection.execute(
            "SELECT conversation_id FROM conversations WHERE kind = 'dm'"
        )
    }
    history: dict[str, list[tuple[str, str, int, str]]] = {}
    for conversation_id, sender, body, timestamp, timestamp_id in connection.execute(
        "SELECT conversation_id, sender, body, time, ts FROM messages ORDER BY time"
    ):
        if conversation_id in dm_ids:
            history.setdefault(conversation_id, []).append(
                (sender, body, timestamp, timestamp_id)
            )
    recipients: dict[str, set[str]] = {}
    for message_id, person_id in connection.execute(
        "SELECT message_id, person_id FROM gmail.recipients"
    ):
        recipients.setdefault(message_id, set()).add(person_id)
    mail = [
        (sender, recipient, timestamp, message_id)
        for message_id, sender, timestamp in connection.execute(
            "SELECT message_id, sender, time FROM gmail.messages"
        )
        for recipient in recipients.get(message_id, ())
    ]

    def request_day(timestamp: int) -> date:
        return epoch + timedelta(days=timestamp // 86_400)

    def next_working_day(value: date) -> date:
        value += timedelta(days=1)
        while value.weekday() >= 5:
            value += timedelta(days=1)
        return value

    def iso(timestamp: int) -> str:
        return (
            datetime(2026, 3, 2, tzinfo=pacific) + timedelta(seconds=timestamp)
        ).isoformat()

    expected = []
    for conversation_id, messages in history.items():
        for position, (asker, body, asked_at, request_ts) in enumerate(messages):
            if body.strip().lower() != (
                "do you still have the sign-in sheet from yesterday?"
            ):
                continue
            (asked_of,) = members[conversation_id] - {asker}
            candidates = [
                (timestamp, "slack", timestamp_id)
                for sender, _, timestamp, timestamp_id in messages[position + 1 :]
                if sender == asked_of and timestamp > asked_at
            ]
            candidates.extend(
                (timestamp, "gmail", message_id)
                for sender, recipient, timestamp, message_id in mail
                if sender == asked_of and recipient == asker and timestamp > asked_at
            )
            first = min(candidates, default=None)
            asked_on = request_day(asked_at)
            deadline = next_working_day(asked_on)
            if first is None:
                outcome = "unresolved"
            elif request_day(first[0]) == asked_on:
                outcome = "same_day"
            elif request_day(first[0]) <= deadline:
                outcome = "next_working_day"
            else:
                outcome = "unresolved"
            expected.append(
                {
                    "request_ts": request_ts,
                    "request_date": asked_on.isoformat(),
                    "asked_by": names[asker],
                    "asked_of": names[asked_of],
                    "first_return_surface": first[1] if first else "none",
                    "first_return_id": first[2] if first else "",
                    "first_return_at": iso(first[0]) if first else "",
                    "outcome": outcome,
                }
            )
    expected.sort(key=lambda record: float(record["request_ts"]))
    outcomes = Counter(record["outcome"] for record in expected)

    assert len(expected) == 71
    assert outcomes == {"same_day": 59, "next_working_day": 10, "unresolved": 2}
    assert document["custody_audit"] == expected


def test_independent_sql_rederives_requests_and_first_response_outcomes() -> None:
    state = BUNDLE / "state"
    connection = sqlite3.connect(f"file:{state / 'slack.db'}?mode=ro", uri=True)
    connection.execute("ATTACH DATABASE ? AS gmail", (str(state / "gmail.db"),))
    query = """
        WITH requests AS (
          SELECT message.chat_message_id, message.conversation_id,
                 message.sender AS asker, member.person_id AS asked_of,
                 message.time AS request_time, message.ts,
                 date('2026-03-02', printf('+%d days', message.time / 86400)) AS day
          FROM messages AS message
          JOIN conversations AS conversation
            ON conversation.conversation_id = message.conversation_id
           AND conversation.kind = 'dm'
          JOIN members AS member
            ON member.conversation_id = message.conversation_id
           AND member.person_id != message.sender
          WHERE lower(trim(message.body)) =
                'do you still have the sign-in sheet from yesterday?'
        ),
        responses AS (
          SELECT request.chat_message_id, message.time
          FROM requests AS request
          JOIN messages AS message
            ON message.conversation_id = request.conversation_id
           AND message.sender = request.asked_of
           AND message.time > request.request_time
          UNION ALL
          SELECT request.chat_message_id, message.time
          FROM requests AS request
          JOIN gmail.messages AS message
            ON message.sender = request.asked_of
           AND message.time > request.request_time
          JOIN gmail.recipients AS recipient
            ON recipient.message_id = message.message_id
           AND recipient.person_id = request.asker
        ),
        first_response AS (
          SELECT chat_message_id, min(time) AS response_time
          FROM responses GROUP BY chat_message_id
        )
        SELECT request.ts, request.day,
               date('2026-03-02', printf('+%d days', response.response_time / 86400))
          FROM requests AS request
          LEFT JOIN first_response AS response USING (chat_message_id)
         ORDER BY request.request_time
    """
    rows = connection.execute(query).fetchall()

    assert len(rows) == 71
    response_day = {ts: day for ts, _, day in rows}
    truth = _truth()
    assert sum(day == asked_on for _, asked_on, day in rows) == 59
    assert response_day["7456314.002498"] == "2026-06-01"
    assert response_day["7569818.002563"] == "2026-06-05"
    assert truth["unresolved_ts"] == ["7456314.002498", "7569818.002563"]


def test_unresolved_means_not_returned_by_next_working_day_not_never_answered() -> None:
    evidence = json.loads((TESTS / "ground_truth.json").read_text())["_evidence"]
    instruction = " ".join((TASK / "instruction.md").read_text().lower().split())

    assert "did not return until after" in evidence["outcomes"]
    assert "even if someone eventually replies later" in instruction


def test_pre_request_or_wrong_direction_mail_cannot_close_custody(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    gmail = sqlite3.connect(bundle / "state" / "gmail.db")
    messages = [
        (
            "pre-request-decoy",
            "pre-request-decoy-thread",
            None,
            "per-diane-okonkwo",
            "sheet",
            "Here it is",
            7_456_314 - 60,
            "Here it is",
        ),
        (
            "wrong-direction-decoy",
            "wrong-direction-decoy-thread",
            None,
            "per-noah-feldstein",
            "sheet",
            "Following up",
            7_456_314 + 60,
            "Following up",
        ),
    ]
    gmail.executemany(
        "INSERT INTO messages(message_id, thread_id, in_reply_to, sender, subject, "
        "body, time, snippet) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        messages,
    )
    gmail.executemany(
        "INSERT INTO recipients(message_id, person_id, kind) VALUES (?, ?, 'to')",
        [
            ("pre-request-decoy", "per-noah-feldstein"),
            ("wrong-direction-decoy", "per-diane-okonkwo"),
        ],
    )
    gmail.commit()
    gmail.close()

    document = _solve_with_state(bundle / "state", bundle / "workspace")
    assert "7456314.002498" in document["unresolved_ts"]
