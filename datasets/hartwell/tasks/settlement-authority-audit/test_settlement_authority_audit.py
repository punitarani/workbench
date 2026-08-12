"""Task-level contracts for the Goldleaf settlement-authority audit."""

import json
import os
import shutil
import sqlite3
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


def _run(tmp_path: Path, producer: Path) -> dict[str, float]:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    subprocess.run(
        ["sh", str(producer)],
        cwd=workspace,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "WORKBENCH_STATE": str(bundle / "state"),
        },
    )
    output = tmp_path / "reward.json"
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


def test_harbor_layout_and_evidence_contract() -> None:
    config = tomllib.loads((TASK / "task.toml").read_text())
    assert config["schema_version"] == "1.3"
    assert config["task"]["name"] == "workbench/settlement-authority-audit"
    assert config["environment"]["docker_image"] == "workbench:dev"
    assert "harness" not in config
    assert config["metadata"]["agent_data_scope"].startswith("Intentionally seatless")
    evidence = config["metadata"]["evidence"]
    assert evidence == {
        "primary_field": "proposal_audit",
        "records": 30,
        "item_fields": ["authority_source_ids"],
        "items": 61,
        "source_surfaces": ["gmail", "slack", "clio"],
        "unique_by": ["message_id"],
        "classification_field": "disposition",
        "classification_counts": {
            "authorized": 9,
            "amount_outside_authority": 3,
            "economic_terms_mismatch": 3,
            "authority_revoked": 4,
            "authority_expired": 3,
            "nonmonetary_terms_mismatch": 4,
            "condition_unmet": 2,
            "authority_not_yet_effective": 2,
        },
        "nonempty_fields": ["message_id", "authority_source_ids"],
    }


def test_oracle_is_grounded_in_the_fresh_projected_record() -> None:
    truth = json.loads((TASK / "tests" / "oracle.json").read_text())
    state = BUNDLE / "state"
    with sqlite3.connect(state / "gmail.db") as connection:
        proposals = connection.execute(
            "SELECT message_id FROM messages "
            "WHERE subject GLOB 'Marigold proposal [0-9][0-9]' ORDER BY time"
        ).fetchall()
        client_authority = connection.execute(
            "SELECT message_id FROM messages WHERE sender='per-olivia-chen' "
            "AND subject LIKE 'Marigold%' ORDER BY time"
        ).fetchall()
    with sqlite3.connect(state / "slack.db") as connection:
        partner_notes = connection.execute(
            "SELECT ts FROM messages WHERE body LIKE '%Project Marigold%' "
            "AND body LIKE '%Olivia%' ORDER BY time"
        ).fetchall()

    assert [row[0] for row in proposals] == [
        record["message_id"] for record in truth["proposal_audit"]
    ]
    authority_sources = {
        source
        for record in truth["authority_timeline"]
        for source in record["source_ids"]
    }
    assert {row[0] for row in client_authority} <= authority_sources
    assert {row[0] for row in partner_notes} <= authority_sources
    assert truth["proposal_count"] == 30
    assert truth["authorized_count"] == 9
    assert truth["breach_count"] == 21


def test_solve_emits_json_without_writing_workspace(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=workspace,
        env={
            **os.environ,
            "WORKBENCH_STATE": str(bundle / "state"),
        },
        check=True,
        capture_output=True,
        text=True,
    )
    assert isinstance(json.loads(completed.stdout), dict)
    assert completed.stderr == ""
    assert not (workspace / "authority.json").exists()


def test_reference_is_exact_and_naive_is_materially_below_half(tmp_path: Path) -> None:
    assert _run(tmp_path / "reference", TASK / "solution" / "solve.sh") == {
        "answer": 1.0,
        "process": 0.0,
    }
    naive = _run(tmp_path / "naive", TASK / "baseline" / "naive.sh")
    assert 0.05 < naive["answer"] < 0.5, naive


def test_reward_wrapper_maps_reward_to_answer(tmp_path: Path) -> None:
    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    workspace = bundle / "workspace"
    subprocess.run(
        ["sh", str(TASK / "solution" / "solve.sh")],
        cwd=workspace,
        check=True,
        env={
            **os.environ,
            "WORKBENCH_STATE": str(bundle / "state"),
        },
    )
    logs = tmp_path / "logs"
    subprocess.run(
        ["sh", str(TASK / "tests" / "test.sh")],
        cwd=workspace,
        check=True,
        env={
            **os.environ,
            "WORKBENCH_WORKSPACE": str(workspace),
            "VERIFIER_LOG_DIR": str(logs),
        },
    )
    assert json.loads((logs / "reward.json").read_text()) == {
        "reward": 1.0,
        "answer": 1.0,
        "process": 0.0,
    }


def test_the_oracle_refuses_an_amount_the_record_does_not_state(
    tmp_path: Path,
) -> None:
    """The oracle derives every figure from the prose, so cross-surface
    drift must break it rather than pass silently.

    The written authority and its contemporaneous partner relay are two
    records of the same grant; the oracle pairs them by the amount each
    states and refuses when they no longer agree. Rewrite the revised-
    authority amount in the email but not in the relay and the oracle must
    refuse to certify -- it cannot invent a matching relay for a figure
    nobody relayed.
    """

    bundle = tmp_path / "bundle"
    shutil.copytree(BUNDLE, bundle)
    with sqlite3.connect(bundle / "state" / "gmail.db") as connection:
        changed = connection.execute(
            "UPDATE messages SET body = replace(body, 'exactly $390,000', "
            "'exactly $999,000') WHERE subject = 'Marigold — revised authority'"
        ).rowcount
    assert changed == 1, "the revised-authority mail was not found to rewrite"

    completed = subprocess.run(
        [sys.executable, str(TASK / "solution" / "solve.py")],
        cwd=bundle / "workspace",
        env={
            "WORKBENCH_STATE": str(bundle / "state"),
            "PATH": f"{Path(sys.executable).parent}:/usr/bin:/bin",
        },
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0, "the oracle certified a figure nobody relayed"
    assert completed.stdout == "", "the oracle emitted an answer despite the drift"
