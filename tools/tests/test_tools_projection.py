"""Projections: the world log becomes per-tool SQLite databases."""

import sqlite3
from pathlib import Path

from projection_fixtures import coherent_events

from workbench.tools import PROJECTORS, project_all
from workbench.tools.coherence import check_coherence


def project_fixture(tmp_path: Path) -> Path:
    out = tmp_path / "state"
    project_all(coherent_events(), out)
    return out


def rows(db: Path, sql: str) -> list[tuple]:
    with sqlite3.connect(db) as connection:
        return connection.execute(sql).fetchall()


def test_all_four_tools_project(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    assert sorted(p.name for p in out.iterdir()) == [
        "chat.db",
        "dms.db",
        "mail.db",
        "matters.db",
    ]


def test_mail_projection(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    messages = rows(
        out / "mail.db",
        "SELECT message_id, thread_id, sender, subject FROM messages ORDER BY time",
    )
    assert len(messages) == 2
    assert messages[0][0] == "msg-000001"
    assert messages[1][2] == "per-tom-okafor"
    recipients = rows(
        out / "mail.db",
        "SELECT person_id, kind FROM recipients WHERE message_id='msg-000001'",
    )
    assert ("per-tom-okafor", "to") in recipients
    assert ("per-meredith-chao", "cc") in recipients
    people = rows(out / "mail.db", "SELECT person_id, name FROM people")
    assert len(people) == 4


def test_chat_projection(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    conversations = rows(
        out / "chat.db", "SELECT conversation_id, name, kind FROM conversations"
    )
    assert conversations == [("cnv-000001", "#legal", "channel")]
    members = rows(
        out / "chat.db",
        "SELECT person_id FROM members WHERE conversation_id='cnv-000001'",
    )
    assert len(members) == 3
    messages = rows(out / "chat.db", "SELECT sender, body FROM messages")
    assert messages == [("per-daniel-reyes", "Taking the NDA review.")]


def test_dms_projection_head_and_history(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    documents = rows(
        out / "dms.db",
        "SELECT document_id, path, head_revision FROM documents",
    )
    assert documents == [("doc-000001", "/legal/playbooks/nda-playbook.md", 2)]
    revisions = rows(
        out / "dms.db",
        "SELECT revision, content FROM revisions WHERE document_id='doc-000001' "
        "ORDER BY revision",
    )
    assert revisions == [(1, "v1"), (2, "v2")]


def test_matters_projection_folds_state(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    tickets = rows(
        out / "matters.db",
        "SELECT ticket_id, status, assignee FROM tickets",
    )
    assert tickets == [("tkt-000001", "in-review", "per-daniel-reyes")]
    history = rows(
        out / "matters.db",
        "SELECT field, old_value, new_value FROM history WHERE ticket_id='tkt-000001'",
    )
    assert ("status", "open", "in-review") in history


def test_sim_events_never_project(tmp_path: Path) -> None:
    assert not any(
        tag.startswith("sim.")
        for tool in PROJECTORS.values()
        for tag in tool.handled_tags
    )
    out = project_fixture(tmp_path)
    for db in out.iterdir():
        with sqlite3.connect(db) as connection:
            tables = [
                r[0]
                for r in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            ]
            for table in tables:
                for row in connection.execute(f"SELECT * FROM {table}"):
                    for value in row:
                        assert "sim." not in str(value)
                        assert "config_hash" not in str(value)


def test_projection_is_content_deterministic(tmp_path: Path) -> None:
    first = project_fixture(tmp_path / "a")
    second = project_fixture(tmp_path / "b")
    for name in ("mail.db", "chat.db", "dms.db", "matters.db"):
        with (
            sqlite3.connect(first / name) as db_a,
            sqlite3.connect(second / name) as db_b,
        ):
            assert list(db_a.iterdump()) == list(db_b.iterdump())


def test_coherence_clean_on_fixture(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    assert check_coherence(out) == ()


def test_coherence_catches_dangling_reference(tmp_path: Path) -> None:
    out = project_fixture(tmp_path)
    with sqlite3.connect(out / "matters.db") as connection:
        connection.execute(
            "UPDATE tickets SET assignee='per-ghost' WHERE ticket_id='tkt-000001'"
        )
    findings = check_coherence(out)
    assert findings, "a dangling person reference must be reported"
    assert any("per-ghost" in f.detail for f in findings)
