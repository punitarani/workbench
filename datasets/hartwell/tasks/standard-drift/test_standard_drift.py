"""Task-level verification: solve.sh earns full reward, the playbook-only
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
from datetime import date, timedelta
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
EPOCH = date(2026, 3, 2)

pytestmark = pytest.mark.skipif(
    not BUNDLE.exists(),
    reason="task bundle not built; run datasets/hartwell/build_tasks.py",
)


def test_harbor_rewardkit_layout_replaces_legacy_grader() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["metadata"]["reference_tool_path_calls"] == 48
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


def _day(timestamp: int) -> str:
    return (EPOCH + timedelta(days=timestamp // 86400)).isoformat()


def _strip_notices(content: str) -> str:
    sections = content.split("\n## ")
    return "\n## ".join(
        [sections[0]]
        + [section for section in sections[1:] if not section.startswith("Notices")]
    )


def test_reference_version_audit_matches_fresh_bundle() -> None:
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
    attachments: dict[str, str] = {}
    for message_id, filename in _rows(
        "gmail.db", "SELECT message_id, filename FROM attachments"
    ):
        attachments[message_id] = f"{attachments.get(message_id, '')} {filename}"
    emails = [
        (
            message_id,
            _day(timestamp),
            f"{subject} {body} {attachments.get(message_id, '')}".lower(),
        )
        for message_id, subject, body, timestamp in _rows(
            "gmail.db", "SELECT message_id, subject, body, time FROM messages"
        )
    ]
    histories: dict[str, list[tuple[int, str, int, int]]] = {}
    for path, number, version, content, timestamp in _rows(
        "imanage.db",
        "SELECT d.path, d.document_number, v.version, v.content, v.time "
        "FROM versions v JOIN documents d ON d.document_id = v.document_id "
        "WHERE d.path LIKE '%/firm/vendor-ndas/%' ORDER BY d.path, v.version",
    ):
        histories.setdefault(path, []).append((version, content, timestamp, number))

    expected = []
    for path, history in histories.items():
        vendor = path.rsplit("/", 1)[-1].removeprefix("mutual-nda-").removesuffix(".md")
        for (previous_version, previous, _, _), (
            version,
            current,
            timestamp,
            number,
        ) in zip(history, history[1:], strict=False):
            assert previous_version + 1 == version
            if previous == current:
                change_class = "unchanged"
            elif _strip_notices(previous) == _strip_notices(current):
                change_class = "notices_only"
            else:
                change_class = "substantive"
            saved = _day(timestamp)
            email_ids = sorted(
                message_id
                for message_id, sent, text in emails
                if sent == saved and vendor in text
            )
            expected.append(
                {
                    "version_id": f"LEGAL!{number}.{version}",
                    "document_path": path,
                    "date": saved,
                    "change_class": change_class,
                    "email_ids": email_ids,
                }
            )
    expected.sort(key=lambda row: (row["document_path"], row["version_id"]))

    assert len(expected) == 16
    assert sum(row["change_class"] == "substantive" for row in expected) == 8
    assert sum(row["change_class"] == "notices_only" for row in expected) == 1
    assert sum(row["change_class"] == "unchanged" for row in expected) == 7
    assert sum(len(row["email_ids"]) for row in expected) == 4
    assert answer["version_audit"] == expected
    assert answer["versions_reviewed"] == 16
    assert answer["substantive_versions"] == 8
    assert answer["notices_only_versions"] == 1
    assert answer["unchanged_versions"] == 7
    assert answer["covered_substantive_versions"] == 4
    assert answer["silent_substantive_versions"] == 4
    assert answer["covering_email_count"] == 4


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
    assert not (workspace / "drift.json").exists()


def test_solution_earns_full_reward(tmp_path: Path) -> None:
    reward = run_grader(tmp_path, TASK / "solution" / "solve.sh")
    assert reward == {"answer": 1.0, "process": 0.0}


def test_naive_baseline_earns_strictly_less(tmp_path: Path) -> None:
    solved = run_grader(tmp_path / "a", TASK / "solution" / "solve.sh")
    naive = run_grader(tmp_path / "b", TASK / "baseline" / "naive.sh")
    assert naive["answer"] < solved["answer"] - 0.4, (
        f"the redline-history citations must discriminate: naive={naive['answer']}"
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


def test_instruction_declares_the_firm_calendar_timezone() -> None:
    instruction = (TASK / "instruction.md").read_text()

    assert "Pacific" in instruction
    assert "UTC" in instruction


def test_instruction_states_the_covering_rule_without_the_trap_checklist() -> None:
    """Cite-what-qualifies, not don't-cite-these-four-things.

    Enumerating the near misses -- thread ids, next-day transmittals,
    Slack notes, other vendors' mail -- converts the same-day rule into a
    checklist and is part of why 9/9 cells got the partition exact. The
    definition of a covering email stays, which is what determines the
    answer.

    Phrases are matched against whitespace-normalized text: the source is
    hard-wrapped, so a raw substring check would pass for the wrong
    reason on any phrase that happens to straddle a line break.
    """

    instruction = " ".join((TASK / "instruction.md").read_text().split())

    assert "any email sent the same calendar day that names that vendor" in instruction
    assert "do not cite a thread ID, next-day transmittal" not in instruction
    assert "neither does an email sent the day after" not in instruction
