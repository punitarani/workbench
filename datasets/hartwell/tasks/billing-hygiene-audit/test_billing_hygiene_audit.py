"""Bundle-backed and Harbor-contract tests for billing-hygiene-audit."""

import importlib.util
import inspect
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tomllib
from datetime import date
from pathlib import Path

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"

# instruction.md: "The certification period is March 2 through June 30,
# 2026, inclusive." Derived here rather than imported from solve.py so
# this re-derivation stays independent of the oracle.
CERTIFICATION_SCOPE_SECONDS = (date(2026, 7, 1) - date(2026, 3, 2)).days * 86_400
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")
PUBLIC_FIELDS = {
    "entries_reviewed",
    "timekeepers_reviewed",
    "person_days_reviewed",
    "cleared_by_communication",
    "cleared_no_corroboration",
    "anomalous_timekeeper_days",
    "anomalous_timekeeper_day_count",
    "anomalous_entry_count",
    "anomalous_minutes_total",
    "anomalous_billed_cents_total",
    "phantom_note_ids",
    "daily_review",
}

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
    assert config["task"]["name"] == "workbench/billing-hygiene-audit"
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
    servers = config["environment"]["mcp_servers"]
    assert servers == [
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
    assert config["verifier"]["user"] == "verifier"
    assert config["verifier"]["network_mode"] == "no-network"


def test_instruction_defines_only_the_corroborated_billable_contract() -> None:
    instruction = (TASK / "instruction.md").read_text().lower()

    for field in PUBLIC_FIELDS:
        assert field in instruction
    for term in (
        "billable",
        "same matter",
        "another person",
        "gmail",
        "slack",
        "individually rounded",
        "phantom_note_ids",
    ):
        assert term in instruction
    assert "unsupported_entry_ids" not in instruction
    assert "unsupported_entries" not in instruction
    assert "unsupported_timekeepers" not in instruction


def test_solve_module_is_importable_annotated_and_side_effect_free(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    solve_path = TASK / "solution" / "solve.py"
    assert solve_path.is_file()
    spec = importlib.util.spec_from_file_location("billing_hygiene_solve", solve_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.chdir(tmp_path)
    spec.loader.exec_module(module)

    assert not (tmp_path / "hygiene.json").exists()
    functions = [
        function
        for _, function in inspect.getmembers(module, inspect.isfunction)
        if function.__module__ == module.__name__
    ]
    assert {function.__name__ for function in functions} >= {"build_hygiene", "main"}
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
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    completed = subprocess.run(
        ["sh", str(TASK / "solution" / "solve.sh")],
        cwd=workspace,
        env={"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout == ""
    assert json.loads((workspace / "hygiene.json").read_text()) == {
        key: value for key, value in _truth().items() if key in PUBLIC_FIELDS
    }


def test_solve_python_emits_document_without_writing_workspace(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=workspace,
        env={"PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin"},
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(completed.stdout) == {
        key: value for key, value in _truth().items() if key in PUBLIC_FIELDS
    }
    assert completed.stderr == ""
    assert not (workspace / "hygiene.json").exists()


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
    assert naive["answer"] > 0.05, naive


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
    days = truth["anomalous_timekeeper_days"]

    assert truth["entries_reviewed"] == 4233
    assert truth["timekeepers_reviewed"] == 8
    assert truth["person_days_reviewed"] == 655
    assert truth["cleared_by_communication"] == 637
    assert truth["cleared_no_corroboration"] == 15
    assert truth["anomalous_timekeeper_day_count"] == 3
    assert days == [
        {
            "date": "2026-04-04",
            "timekeeper": "Eleanor Hartwell",
            "entry_ids": [1318, 1319],
            "matter_numbers": ["00001-MeridianBioLabs"],
            "minutes": 126,
            "billed_cents": 141750,
        },
        {
            "date": "2026-05-20",
            "timekeeper": "Noah Feldstein",
            "entry_ids": [2884, 2885, 2887, 2896, 2898, 2899, 2910, 2915, 2923],
            "matter_numbers": [
                "00009-LumenSoftware",
                "00006-NorthgateMedicalGroup",
            ],
            "minutes": 414,
            "billed_cents": 251850,
        },
        {
            "date": "2026-06-15",
            "timekeeper": "Diane Okonkwo",
            "entry_ids": [3753, 3760, 3761, 3762, 3768, 3771, 3783],
            "matter_numbers": [
                "00003-VeridianEnergyCooperative",
                "00006-NorthgateMedicalGroup",
                "00007-PelicanBayMarina",
            ],
            "minutes": 336,
            "billed_cents": 294000,
        },
    ]
    assert truth["anomalous_entry_count"] == 18
    assert truth["anomalous_minutes_total"] == 876
    assert truth["anomalous_billed_cents_total"] == 687600
    assert truth["phantom_note_ids"] == [176]


def test_reference_daily_review_matches_fresh_bundle() -> None:
    state = BUNDLE / "state"
    connection = sqlite3.connect(f"file:{state / 'clio.db'}?mode=ro", uri=True)
    connection.execute("ATTACH DATABASE ? AS gmail", (str(state / "gmail.db"),))
    connection.execute("ATTACH DATABASE ? AS slack", (str(state / "slack.db"),))
    names = dict(connection.execute("SELECT person_id, name FROM people"))
    matter_numbers = dict(
        connection.execute("SELECT ticket_id, display_number FROM matters")
    )
    activities = connection.execute(
        "SELECT ROW_NUMBER() OVER (ORDER BY time), ticket_id, person, time, "
        "billable FROM activities WHERE time < ? ORDER BY time",
        (CERTIFICATION_SCOPE_SECONDS,),
    ).fetchall()
    notes = connection.execute(
        "SELECT ticket_id, author, time FROM notes WHERE time < ? ORDER BY time",
        (CERTIFICATION_SCOPE_SECONDS,),
    ).fetchall()

    def day(timestamp: int) -> str:
        return connection.execute(
            "SELECT date('2026-03-02', printf('+%d days', ? / 86400))",
            (timestamp,),
        ).fetchone()[0]

    sent_gmail: dict[tuple[str, str], list[str]] = {}
    for message_id, sender, timestamp in connection.execute(
        "SELECT message_id, sender, time FROM gmail.messages WHERE time < ? "
        "ORDER BY time, message_id",
        (CERTIFICATION_SCOPE_SECONDS,),
    ):
        sent_gmail.setdefault((sender, day(timestamp)), []).append(message_id)
    sent_slack: dict[tuple[str, str], list[str]] = {}
    for ts, sender, timestamp in connection.execute(
        "SELECT ts, sender, time FROM slack.messages WHERE time < ? ORDER BY time, ts",
        (CERTIFICATION_SCOPE_SECONDS,),
    ):
        sent_slack.setdefault((sender, day(timestamp)), []).append(ts)

    participants: dict[tuple[str, str], set[str]] = {}
    for _, ticket_id, person, timestamp, _ in activities:
        participants.setdefault((ticket_id, day(timestamp)), set()).add(person)
    for ticket_id, author, timestamp in notes:
        participants.setdefault((ticket_id, day(timestamp)), set()).add(author)

    grouped: dict[tuple[str, str], list[tuple[int, str]]] = {}
    for activity_id, ticket_id, person, timestamp, billable in activities:
        if billable:
            grouped.setdefault((day(timestamp), person), []).append(
                (activity_id, ticket_id)
            )

    daily_review = []
    for (activity_day, person), entries in sorted(
        grouped.items(), key=lambda item: (item[0][0], names[item[0][1]])
    ):
        corroborated = [
            entry
            for entry in entries
            if participants[(entry[1], activity_day)] - {person}
        ]
        gmail_ids = sent_gmail.get((person, activity_day), [])
        slack_ts = sent_slack.get((person, activity_day), [])
        if gmail_ids or slack_ts:
            disposition = "cleared_by_communication"
        elif corroborated:
            disposition = "anomalous"
        else:
            disposition = "cleared_no_corroboration"
        daily_review.append(
            {
                "date": activity_day,
                "timekeeper": names[person],
                "billable_entry_ids": [entry[0] for entry in entries],
                "sent_gmail_ids": gmail_ids,
                "sent_slack_ts": slack_ts,
                "corroborated_entry_ids": [entry[0] for entry in corroborated],
                "corroborated_matter_numbers": list(
                    dict.fromkeys(matter_numbers[entry[1]] for entry in corroborated)
                ),
                "disposition": disposition,
            }
        )

    truth = _truth()
    assert len(daily_review) == truth["person_days_reviewed"] == 655
    assert sum(len(row["billable_entry_ids"]) for row in daily_review) == 4233
    assert (
        sum(row["disposition"] == "cleared_by_communication" for row in daily_review)
        == 637
    )
    assert (
        sum(row["disposition"] == "cleared_no_corroboration" for row in daily_review)
        == 15
    )
    assert sum(row["disposition"] == "anomalous" for row in daily_review) == 3
    assert daily_review == truth["daily_review"]


def test_independent_sql_asserts_corroborated_entry_and_note_sets() -> None:
    state = BUNDLE / "state"
    connection = sqlite3.connect(f"file:{state / 'clio.db'}?mode=ro", uri=True)
    connection.execute("ATTACH DATABASE ? AS gmail", (str(state / "gmail.db"),))
    connection.execute("ATTACH DATABASE ? AS slack", (str(state / "slack.db"),))
    query = f"""
        WITH indexed AS (
          SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, activities.*,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM activities WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        ),
        messages AS (
          SELECT sender AS person,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM gmail.messages WHERE time < {CERTIFICATION_SCOPE_SECONDS}
          UNION
          SELECT sender,
                 date('2026-03-02', printf('+%d days', time / 86400))
          FROM slack.messages WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        ),
        events AS (
          SELECT ticket_id, person,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM activities WHERE time < {CERTIFICATION_SCOPE_SECONDS}
          UNION ALL
          SELECT ticket_id, author,
                 date('2026-03-02', printf('+%d days', time / 86400))
          FROM notes WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        )
        SELECT indexed.id
        FROM indexed
        WHERE indexed.billable = 1
          AND NOT EXISTS (
            SELECT 1 FROM messages
            WHERE messages.person = indexed.person
              AND messages.day = indexed.day
          )
          AND EXISTS (
            SELECT 1 FROM events
            WHERE events.ticket_id = indexed.ticket_id
              AND events.day = indexed.day
              AND events.person != indexed.person
          )
        ORDER BY indexed.id
    """
    activity_ids = [row[0] for row in connection.execute(query)]
    note_query = f"""
        WITH indexed AS (
          SELECT ROW_NUMBER() OVER (ORDER BY time) AS id, notes.*,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM notes WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        ),
        messages AS (
          SELECT sender AS person,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM gmail.messages WHERE time < {CERTIFICATION_SCOPE_SECONDS}
          UNION
          SELECT sender,
                 date('2026-03-02', printf('+%d days', time / 86400))
          FROM slack.messages WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        ),
        events AS (
          SELECT ticket_id, person,
                 date('2026-03-02', printf('+%d days', time / 86400)) AS day
          FROM activities WHERE time < {CERTIFICATION_SCOPE_SECONDS}
          UNION ALL
          SELECT ticket_id, author,
                 date('2026-03-02', printf('+%d days', time / 86400))
          FROM notes WHERE time < {CERTIFICATION_SCOPE_SECONDS}
        )
        SELECT indexed.id
        FROM indexed
        WHERE NOT EXISTS (
            SELECT 1 FROM messages
            WHERE messages.person = indexed.author
              AND messages.day = indexed.day
          )
          AND EXISTS (
            SELECT 1 FROM events
            WHERE events.ticket_id = indexed.ticket_id
              AND events.day = indexed.day
              AND events.person != indexed.author
          )
        ORDER BY indexed.id
    """
    note_ids = [row[0] for row in connection.execute(note_query)]

    assert activity_ids == [
        1318,
        1319,
        2884,
        2885,
        2887,
        2896,
        2898,
        2899,
        2910,
        2915,
        2923,
        3753,
        3760,
        3761,
        3762,
        3768,
        3771,
        3783,
    ]
    assert note_ids == [176]
