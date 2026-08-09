"""MCP servers over the projected databases: read surfaces plus leakage audit."""

import json
from pathlib import Path

import pytest
from projection_fixtures import coherent_events

from workbench.tools import build_server, project_all

OFFSTAGE_MARKERS = ("sim.", "share_policy", "config_hash", "seed_root")


@pytest.fixture
def state_dir(tmp_path: Path) -> Path:
    out = tmp_path / "state"
    project_all(coherent_events(), out)
    return out


async def call(server, name: str, arguments: dict | None = None) -> list:
    """Returns the parsed content items; list returns arrive one item each."""
    result = await server.call_tool(name, arguments or {})
    assert not result.is_error, result
    return [json.loads(c.text) for c in result.content if hasattr(c, "text")]


async def test_mail_server_reads_threads(state_dir: Path) -> None:
    server = build_server("mail", state_dir / "mail.db")
    threads = await call(server, "list_threads")
    assert len(threads) == 1
    assert threads[0]["thread_id"] == "thr-000001"
    assert threads[0]["message_count"] == 2

    thread = await call(server, "read_thread", {"thread_id": "thr-000001"})
    assert [m["message_id"] for m in thread] == ["msg-000001", "msg-000002"]
    assert thread[0]["to"] == ["per-tom-okafor"]

    hits = await call(server, "search_mail", {"query": "NDA"})
    assert len(hits) == 2


async def test_chat_server_reads_conversations(state_dir: Path) -> None:
    server = build_server("chat", state_dir / "chat.db")
    conversations = await call(server, "list_conversations")
    assert conversations[0]["name"] == "#legal"
    messages = await call(
        server, "read_conversation", {"conversation_id": "cnv-000001"}
    )
    assert messages[0]["body"] == "Taking the NDA review."


async def test_dms_server_reads_documents(state_dir: Path) -> None:
    server = build_server("dms", state_dir / "dms.db")
    documents = await call(server, "list_documents")
    assert documents[0]["path"] == "/legal/playbooks/nda-playbook.md"
    [document] = await call(server, "read_document", {"ref": "doc-000001"})
    assert document["content"] == "v2"
    [by_path] = await call(
        server, "read_document", {"ref": "/legal/playbooks/nda-playbook.md"}
    )
    assert by_path["document_id"] == "doc-000001"
    history = await call(server, "document_history", {"document_id": "doc-000001"})
    assert [r["revision"] for r in history] == [1, 2]


async def test_matters_server_reads_tickets(state_dir: Path) -> None:
    server = build_server("matters", state_dir / "matters.db")
    tickets = await call(server, "list_tickets")
    assert tickets[0]["status"] == "in-review"
    [ticket] = await call(server, "read_ticket", {"ticket_id": "tkt-000001"})
    assert ticket["title"] == "Review NDA"
    assert ticket["history"][0]["field"] == "status"


async def test_every_server_has_directory_and_only_read_tools(
    state_dir: Path,
) -> None:
    for name in ("mail", "chat", "dms", "matters"):
        server = build_server(name, state_dir / f"{name}.db")
        people = await call(server, "directory")
        assert len(people) == 4
        tools = await server.list_tools()
        for tool in tools:
            assert not any(
                verb in tool.name
                for verb in ("send", "create", "update", "delete", "write", "post")
            ), f"{name} exposes a write tool in the read-only phase: {tool.name}"


async def test_leakage_audit_no_offstage_markers(state_dir: Path) -> None:
    arguments = {
        "read_thread": {"thread_id": "thr-000001"},
        "search_mail": {"query": "a"},
        "read_conversation": {"conversation_id": "cnv-000001"},
        "search_chat": {"query": "a"},
        "read_document": {"ref": "doc-000001"},
        "document_history": {"document_id": "doc-000001"},
        "read_ticket": {"ticket_id": "tkt-000001"},
    }
    for name in ("mail", "chat", "dms", "matters"):
        server = build_server(name, state_dir / f"{name}.db")
        for tool in await server.list_tools():
            result = await server.call_tool(tool.name, arguments.get(tool.name, {}))
            text = "".join(c.text for c in result.content if hasattr(c, "text"))
            for marker in OFFSTAGE_MARKERS:
                assert marker not in text, f"{name}.{tool.name} leaked {marker!r}"


async def test_unknown_ids_error_cleanly(state_dir: Path) -> None:
    server = build_server("mail", state_dir / "mail.db")
    with pytest.raises(Exception, match="thr-999999"):
        await server.call_tool("read_thread", {"thread_id": "thr-999999"})
