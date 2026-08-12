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

# instruction.md: "Sweep every one-to-one conversation from March through
# June." Derived here rather than imported from solve.py so this
# re-derivation stays independent of the oracle.
REVIEW_SCOPE_SECONDS = (date(2026, 7, 1) - EPOCH).days * 86_400
# A reply is the *read* only if it delivers a verdict on the draft (a marker
# in chat, or a "Draft read" email); a bare acknowledgement is not.
REVIEW_MARKERS = (
    "send it out",
    "good to go",
    "one redline",
    "ready to go out",
    "no changes from me",
    "ship it",
    "clear to file",
    "signed off on the draft",
)
EMAIL_MARKER = "draft read"
HOLIDAYS = frozenset({date(2026, 5, 25), date(2026, 6, 19)})

pytestmark = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def test_harbor_rewardkit_layout_replaces_legacy_grader() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["metadata"]["reference_tool_path_calls"] == 57
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


def _rows(database: str, sql: str, *params: object) -> list[tuple]:
    with sqlite3.connect(BUNDLE / "state" / database) as connection:
        return connection.execute(sql, params).fetchall()


def _day(timestamp: int) -> date:
    return EPOCH + timedelta(days=timestamp // 86_400)


def _iso(timestamp: int) -> str:
    return (
        datetime(2026, 3, 2, tzinfo=PACIFIC) + timedelta(seconds=timestamp)
    ).isoformat()


def _next_working_day(value: date) -> date:
    value += timedelta(days=1)
    while value.weekday() >= 5 or value in HOLIDAYS:
        value += timedelta(days=1)
    return value


def _is_read(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in REVIEW_MARKERS)


def test_reference_response_audit_matches_fresh_bundle() -> None:
    """Re-derive the ledger independently of solve.py with the same rules:
    the read is a verdict-bearing reply (a marker in chat or a 'Draft read'
    email, never a bare acknowledgement), matched to the request instance it
    answers by timing across surfaces, then classified against a holiday-aware
    Pacific next-working-day deadline."""
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
    requests = []
    reads: list[tuple[int, str, str, str, str]] = []
    for conversation_id, sender, body, timestamp, timestamp_id in _rows(
        "slack.db",
        "SELECT conversation_id, sender, body, time, ts FROM messages "
        "WHERE time < ? ORDER BY time",
        REVIEW_SCOPE_SECONDS,
    ):
        if conversation_id not in dm_ids or len(members[conversation_id]) != 2:
            continue
        (other,) = members[conversation_id] - {sender}
        if body.strip().lower() == REQUEST:
            requests.append(
                {
                    "ts": timestamp_id,
                    "time": timestamp,
                    "asked_by": sender,
                    "asked_of": other,
                }
            )
        if _is_read(body):
            reads.append((timestamp, "slack", timestamp_id, other, sender))
    recipients: dict[str, set[str]] = {}
    for message_id, person_id in _rows(
        "gmail.db", "SELECT message_id, person_id FROM recipients"
    ):
        recipients.setdefault(message_id, set()).add(person_id)
    for message_id, sender, subject, timestamp in _rows(
        "gmail.db",
        "SELECT message_id, sender, subject, time FROM messages WHERE time < ?",
        REVIEW_SCOPE_SECONDS,
    ):
        if EMAIL_MARKER in subject.lower():
            for recipient in recipients.get(message_id, ()):
                reads.append((timestamp, "gmail", message_id, recipient, sender))

    by_pair: dict[tuple[str, str], list[int]] = {}
    for index, request in enumerate(requests):
        by_pair.setdefault((request["asked_by"], request["asked_of"]), []).append(index)
    for indices in by_pair.values():
        indices.sort(key=lambda index: requests[index]["time"])
    for request in requests:
        request["read"] = None
    for timestamp, surface, identifier, asker, reviewer in sorted(reads):
        owner = None
        for index in by_pair.get((asker, reviewer), ()):
            if requests[index]["time"] < timestamp:
                owner = index
        if owner is None:
            continue
        current = requests[owner]["read"]
        if current is None or timestamp < current[0]:
            requests[owner]["read"] = (timestamp, surface, identifier)

    expected = []
    for request in requests:
        asked_on = _day(request["time"])
        deadline = _next_working_day(asked_on)
        read = request["read"]
        if read is None:
            surface, identifier, at, outcome = "none", "", "", "unanswered"
        else:
            when, surface, identifier = read
            at = _iso(when)
            read_day = _day(when)
            if read_day == asked_on:
                outcome = "same_day"
            elif read_day <= deadline:
                outcome = "next_working_day"
            else:
                outcome = "unanswered"
        expected.append(
            {
                "request_ts": request["ts"],
                "request_date": asked_on.isoformat(),
                "asked_by": names[request["asked_by"]],
                "asked_of": names[request["asked_of"]],
                "first_response_surface": surface,
                "first_response_id": identifier,
                "first_response_at": at,
                "outcome": outcome,
            }
        )
    expected.sort(key=lambda row: float(row["request_ts"]))
    outcomes = Counter(row["outcome"] for row in expected)
    surfaces = Counter(row["first_response_surface"] for row in expected)

    assert len(expected) == 75
    assert outcomes == {"same_day": 32, "next_working_day": 34, "unanswered": 9}
    assert surfaces == {"slack": 59, "gmail": 11, "none": 5}
    assert answer["response_audit"] == expected
    assert answer["requests_reviewed"] == 75
    assert answer["answered_same_day"] == 32
    assert answer["answered_next_working_day"] == 34
    assert answer["unanswered_by_deadline"] == 9


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
        f"the traps must discriminate: naive={naive['answer']}"
    )
    assert naive["answer"] > 0.01


def test_missing_deliverable_scores_zero(tmp_path: Path) -> None:
    empty = tmp_path / "noop.sh"
    empty.write_text("true\n")
    reward = run_grader(tmp_path, empty)
    assert reward == {"answer": 0.0, "process": 0.0}


def test_grading_is_deterministic(tmp_path: Path) -> None:
    first = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    second = run_grader(tmp_path / "b", TASK / "solution" / "solve.sh")
    assert first == second


def test_the_honest_shortcut_loses_most_of_the_ledger(tmp_path: Path) -> None:
    """The surface reading now fails the majority of rows.

    ``honest-shortcut.sh`` carries the plausible surface reading all the way
    through the ledger: it counts the first reply back (acknowledgements and
    chatter included), reads Slack only, dates timestamps by the stored clock,
    and skips weekends but not holidays. That is exactly the reading the arc is
    built to punish. Where the old fabric let it land ~0.67, the per-row traps
    -- the acknowledgement-then-read gap, the cross-surface mail reads, the
    evening reads whose UTC date rolls over, the holiday-skipped deadlines, and
    the re-sent requests -- now cost it most of its credit. It lands ~0.24, far
    below the certified 1.0, which is the point: the traps bite.
    """

    scored = run_grader(tmp_path, TASK / "baseline" / "honest-shortcut.sh")

    assert scored["answer"] < 0.35, (
        f"the surface reading must lose the majority of the ledger, "
        f"measured {scored['answer']}"
    )
