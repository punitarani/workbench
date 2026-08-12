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
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

TASK = Path(__file__).parent
BUNDLE = TASK / "bundle"
TESTS = TASK / "tests"
REWARDKIT = shutil.which("rewardkit")

# instruction.md: "Every instance in every Slack direct-message conversation
# from March through June is in scope." Derived here rather than imported
# from solve.py so this re-derivation stays independent of the oracle.
REVIEW_SCOPE_SECONDS = (date(2026, 7, 1) - date(2026, 3, 2)).days * 86_400
REQUEST = "do you still have the sign-in sheet from yesterday?"
# A holder reply is the *return* only if it confirms the sheet is physically
# back at the front desk (a marker in chat, or a "Sign-in sheet returned"
# email); a bare acknowledgement that the holder still has it is not.
RETURN_MARKERS = (
    "back at reception",
    "back on the reception desk",
    "back on the front desk",
    "back in the reception binder",
    "back on the sign-in clipboard",
    "back downstairs at reception",
    "returned it to the front desk",
    "back on the desk out front",
)
EMAIL_MARKER = "sign-in sheet returned"
HOLIDAYS = frozenset({date(2026, 5, 25), date(2026, 6, 19)})
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
    assert truth["unresolved_ts"] == [
        "1775493180.000000",
        "1778262060.000000",
    ]
    assert truth["same_day_breach_ts"] == [record["ts"] for record in breaches]
    assert all(set(record) == BREACH_FIELDS for record in breaches)


def _is_return(body: str) -> bool:
    lowered = body.lower()
    return any(marker in lowered for marker in RETURN_MARKERS)


def _next_working_day(value: date) -> date:
    value += timedelta(days=1)
    while value.weekday() >= 5 or value in HOLIDAYS:
        value += timedelta(days=1)
    return value


def test_reference_custody_audit_matches_fresh_bundle() -> None:
    """Re-derive the ledger independently of solve.py with the same rules:
    the return is a marker-bearing message (a reception marker in chat, or a
    'Sign-in sheet returned' email, never a bare acknowledgement), matched to
    the request instance it answers by timing across surfaces, then classified
    against a holiday-aware Pacific next-working-day custody deadline."""
    state = BUNDLE / "state"
    document = _solve_with_state(state, BUNDLE / "workspace")
    epoch = date(2026, 3, 2)
    pacific = ZoneInfo("America/Los_Angeles")
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
    requests: list[dict] = []
    returns: list[tuple[int, str, str, str, str]] = []
    for conversation_id, sender, body, timestamp, timestamp_id in connection.execute(
        "SELECT conversation_id, sender, body, time, ts FROM messages "
        "WHERE time < ? ORDER BY time, ts",
        (REVIEW_SCOPE_SECONDS,),
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
        if _is_return(body):
            returns.append((timestamp, "slack", timestamp_id, other, sender))
    recipients: dict[str, set[str]] = {}
    for message_id, person_id in connection.execute(
        "SELECT message_id, person_id FROM gmail.recipients"
    ):
        recipients.setdefault(message_id, set()).add(person_id)
    for message_id, sender, subject, timestamp in connection.execute(
        "SELECT message_id, sender, subject, time FROM gmail.messages WHERE time < ?",
        (REVIEW_SCOPE_SECONDS,),
    ):
        if EMAIL_MARKER in subject.lower():
            for recipient in recipients.get(message_id, ()):
                returns.append((timestamp, "gmail", message_id, recipient, sender))

    by_pair: dict[tuple[str, str], list[int]] = {}
    for index, request in enumerate(requests):
        by_pair.setdefault((request["asked_by"], request["asked_of"]), []).append(index)
    for indices in by_pair.values():
        indices.sort(key=lambda index: requests[index]["time"])
    for request in requests:
        request["return"] = None
    for timestamp, surface, identifier, asker, holder in sorted(returns):
        owner = None
        for index in by_pair.get((asker, holder), ()):
            if requests[index]["time"] < timestamp:
                owner = index
        if owner is None:
            continue
        current = requests[owner]["return"]
        if current is None or timestamp < current[0]:
            requests[owner]["return"] = (timestamp, surface, identifier)

    def request_day(timestamp: int) -> date:
        return epoch + timedelta(days=timestamp // 86_400)

    def iso(timestamp: int) -> str:
        return (
            datetime(2026, 3, 2, tzinfo=pacific) + timedelta(seconds=timestamp)
        ).isoformat()

    expected = []
    for request in requests:
        asked_on = request_day(request["time"])
        deadline = _next_working_day(asked_on)
        returned = request["return"]
        if returned is None:
            surface, identifier, at, outcome = "none", "", "", "unresolved"
        else:
            when, surface, identifier = returned
            at = iso(when)
            return_day = request_day(when)
            if return_day == asked_on:
                outcome = "same_day"
            elif return_day <= deadline:
                outcome = "next_working_day"
            else:
                outcome = "unresolved"
        expected.append(
            {
                "request_ts": request["ts"],
                "request_date": asked_on.isoformat(),
                "asked_by": names[request["asked_by"]],
                "asked_of": names[request["asked_of"]],
                "first_return_surface": surface,
                "first_return_id": identifier,
                "first_return_at": at,
                "outcome": outcome,
            }
        )
    expected.sort(key=lambda record: float(record["request_ts"]))
    outcomes = Counter(record["outcome"] for record in expected)
    surfaces = Counter(record["first_return_surface"] for record in expected)

    assert len(expected) == 71
    assert outcomes == {"same_day": 59, "next_working_day": 10, "unresolved": 2}
    assert surfaces == {"slack": 66, "gmail": 4, "none": 1}
    assert document["custody_audit"] == expected


def test_independent_sql_rederives_the_request_and_return_population() -> None:
    """An independent SQL cross-check of the fabric population the oracle reads:
    exactly 71 standing-form requests in the DM lanes, and the marker-bearing
    returns split 66 in-lane chat and 4 directed 'Sign-in sheet returned'
    emails -- the counts the certified oracle's surface split rests on."""
    state = BUNDLE / "state"
    connection = sqlite3.connect(f"file:{state / 'slack.db'}?mode=ro", uri=True)
    connection.execute("ATTACH DATABASE ? AS gmail", (str(state / "gmail.db"),))
    (request_count,) = connection.execute(
        f"""
        SELECT count(*)
          FROM messages AS message
          JOIN conversations AS conversation
            ON conversation.conversation_id = message.conversation_id
           AND conversation.kind = 'dm'
         WHERE lower(trim(message.body)) = ?
           AND message.time < {REVIEW_SCOPE_SECONDS}
        """,
        (REQUEST,),
    ).fetchone()
    assert request_count == 71

    marker_clause = " OR ".join("instr(lower(message.body), ?)" for _ in RETURN_MARKERS)
    (chat_returns,) = connection.execute(
        f"""
        SELECT count(*)
          FROM messages AS message
          JOIN conversations AS conversation
            ON conversation.conversation_id = message.conversation_id
           AND conversation.kind = 'dm'
         WHERE ({marker_clause})
           AND message.time < {REVIEW_SCOPE_SECONDS}
        """,
        RETURN_MARKERS,
    ).fetchone()
    assert chat_returns == 66

    (mail_returns,) = connection.execute(
        f"""
        SELECT count(*)
          FROM gmail.messages AS message
         WHERE instr(lower(message.subject), ?)
           AND message.time < {REVIEW_SCOPE_SECONDS}
        """,
        (EMAIL_MARKER,),
    ).fetchone()
    assert mail_returns == 4

    truth = _truth()
    surfaces = Counter(
        record["first_return_surface"] for record in truth["custody_audit"]
    )
    assert surfaces == {"slack": 66, "gmail": 4, "none": 1}


def test_unresolved_means_not_returned_by_next_working_day_not_never_answered() -> None:
    evidence = json.loads((TESTS / "ground_truth.json").read_text())["_evidence"]
    instruction = " ".join((TASK / "instruction.md").read_text().lower().split())

    assert "did not return until after" in evidence["outcomes"]
    assert "even if someone eventually replies later" in instruction


def test_pre_request_or_wrong_direction_mail_cannot_close_custody(
    tmp_path: Path,
) -> None:
    # The LATE breach: Peter Novak asked Noah Feldstein, who returned the sheet
    # two working days later -- past the deadline, so unresolved. A marked
    # "Sign-in sheet returned" email that either predates the request or runs
    # the wrong direction (asker -> holder) must not close it.
    target_ts = "1778262060.000000"
    holder, asker = "per-noah-feldstein", "per-peter-novak"
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    slack = sqlite3.connect(f"file:{bundle / 'state' / 'slack.db'}?mode=ro", uri=True)
    (request_time,) = slack.execute(
        "SELECT time FROM messages WHERE ts = ?", (target_ts,)
    ).fetchone()
    slack.close()

    gmail = sqlite3.connect(bundle / "state" / "gmail.db")
    messages = [
        (
            "pre-request-decoy",
            "pre-request-decoy-thread",
            None,
            holder,
            "Sign-in sheet returned",
            "Brought it down.",
            request_time - 60,
            "Brought it down.",
        ),
        (
            "wrong-direction-decoy",
            "wrong-direction-decoy-thread",
            None,
            asker,
            "Sign-in sheet returned",
            "Any update on the sheet?",
            request_time + 60,
            "Any update on the sheet?",
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
            ("pre-request-decoy", asker),
            ("wrong-direction-decoy", holder),
        ],
    )
    gmail.commit()
    gmail.close()

    document = _solve_with_state(bundle / "state", bundle / "workspace")
    assert target_ts in document["unresolved_ts"]


def test_the_honest_shortcut_loses_most_of_the_ledger(tmp_path: Path) -> None:
    """The surface reading now fails the majority of the ledger.

    ``honest-shortcut.sh`` carries the plausible surface reading all the way
    through the work product: it counts the first reply back from the person
    asked (acknowledgements included, so "still have it up here" reads as a
    return), reads Slack only, dates timestamps by the stored Pacific clock,
    and skips weekends but not holidays. That is exactly the reading the arc is
    built to punish. Where the old fabric let it land ~0.74, the per-row traps
    -- the acknowledgement-then-return gap, the cross-surface mail returns, the
    holiday-skipped deadlines, and the re-sent request -- now cost it most of
    its credit. It lands well below half, far from the certified 1.0, which is
    the point: the traps bite.
    """

    workspace = _produce(tmp_path, TASK / "baseline" / "honest-shortcut.sh")
    scored, _ = _score(workspace, tmp_path / "logs")

    assert scored["answer"] < 0.4, (
        f"the surface reading must lose the majority of the ledger, "
        f"measured {scored['answer']}"
    )
