"""Environment assembly: world log in, environment bundle out."""

import json
import sys
import tomllib
from pathlib import Path

import pytest
from worldlog_fixtures import coherent_events

from core.errors import WorldLogIntegrityError
from core.worldlog import WorldLogWriter
from environment import materialize
from tools import REGISTRY, check_coherence

SYSTEMS = {system.name for system in REGISTRY}


def write_log(tmp_path: Path) -> Path:
    log_path = tmp_path / "world.jsonl"
    with WorldLogWriter(log_path) as writer:
        for event in coherent_events():
            writer.append(event)
    return log_path


def test_materialize_produces_bundle(tmp_path: Path) -> None:
    log_path = write_log(tmp_path)
    out = tmp_path / "bundle"
    result = materialize(log_path, out)

    # The registry is the single source of truth for what a bundle carries.
    assert sorted(p.name for p in (out / "state").iterdir()) == sorted(
        f"{name}.db" for name in SYSTEMS
    )
    assert check_coherence(out / "state") == ()

    config = json.loads((out / "mcp.json").read_text())
    servers = config["mcpServers"]
    assert set(servers) == SYSTEMS
    for name, spec in servers.items():
        assert spec["args"][3:5] == ["--db", f"state/{name}.db"]

    environment = tomllib.loads((out / "environment.toml").read_text())
    assert set(environment["tools"]["compose"]) == SYSTEMS
    assert environment["agent"]["workspace"] == "workspace"
    assert result.event_count == len(coherent_events())
    assert result.bundle == out
    assert result.agent_workspace == out / "workspace"


def test_agent_workspace_holds_no_environment_internals(tmp_path: Path) -> None:
    """The agent's cwd is the bundle's workspace/ — the tool databases and
    the server wiring are siblings of it, never inside it."""

    log_path = write_log(tmp_path)
    out = tmp_path / "bundle"
    result = materialize(log_path, out)
    agent_workspace = result.agent_workspace

    assert list(agent_workspace.rglob("*.db")) == []
    assert list(agent_workspace.rglob("mcp.json")) == []
    assert list(agent_workspace.rglob(".mcp.json")) == []
    assert list(agent_workspace.rglob("environment.toml")) == []
    assert not (agent_workspace / "state").exists()
    assert (out / "state").is_dir()
    assert (out / "state").parent == agent_workspace.parent


def test_materialize_writes_document_head_files(tmp_path: Path) -> None:
    log_path = write_log(tmp_path)
    out = tmp_path / "bundle"
    result = materialize(log_path, out)

    # The fixture's one document lives at /legal/playbooks/nda-playbook.md
    # and was revised to "v2"; the head version becomes a real file **at
    # the path the document system serves for it**.
    #
    # This assertion used to expect `workspace/legal/nda-playbook.md` — the
    # top-level segment only — and so encoded the defect rather than the
    # rule. The file room flattened every document into its workspace while
    # iManage served the author's declared path, and on a six-month world
    # 304 of 308 documents were served at a location that did not exist:
    # an agent that read a path from the document system and opened it
    # failed 98.7% of the time. Every document id resolved, so nothing
    # referential could see it, and this test passed throughout.
    #
    # Flattening cost the file room its shape as well. With every matter
    # sharing one namespace the obvious filenames collided and later
    # documents overwrote earlier ones — 377 documents produced 341 files.
    # They now produce 377.
    target = out / "workspace" / "legal" / "playbooks" / "nda-playbook.md"
    assert target.read_text(encoding="utf-8") == "v2"
    assert result.document_files == 1
    assert [p.name for p in result.agent_workspace.iterdir()] == ["legal"]


def test_a_document_is_filed_where_its_profile_says_it_is(tmp_path: Path) -> None:
    """The served path and the file are one string, not two.

    The regression guard for the defect above, asserted as the property
    rather than as one fixture path: whatever iManage reports as a
    document's path, opening exactly that under the workspace must find the
    bytes. A writer that recomputes a location — from the workspace column,
    from the basename, from the declared extension — passes the assertion
    above and fails this one the moment a document sits two folders deep.
    """

    import sqlite3

    out = tmp_path / "bundle"
    result = materialize(write_log(tmp_path), out)
    with sqlite3.connect(out / "state" / "imanage.db") as connection:
        served = [row[0] for row in connection.execute("SELECT path FROM documents")]
    assert served, "the fixture must project at least one document"
    for path in served:
        assert (result.agent_workspace / path).is_file(), path


def test_materialize_refuses_invalid_log(tmp_path: Path) -> None:
    log_path = write_log(tmp_path)
    lines = log_path.read_text().splitlines()
    # Drop a person record the rest of the log references.
    del lines[1]
    broken = tmp_path / "broken.jsonl"
    broken.write_text("\n".join(lines) + "\n")
    with pytest.raises(WorldLogIntegrityError):
        materialize(broken, tmp_path / "ws")


async def test_stdio_server_end_to_end(tmp_path: Path) -> None:
    """Spawn a real server subprocess and drive it with a real MCP client."""
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    log_path = write_log(tmp_path)
    out = tmp_path / "bundle"
    materialize(log_path, out)

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "tools.serve", "gmail", "--db", "state/gmail.db"],
        cwd=str(out),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {
                "search_threads",
                "get_thread",
                "get_message",
                "list_labels",
            } <= names
            result = await session.call_tool("get_thread", {"threadId": "thr-000001"})
            text = "".join(c.text for c in result.content if hasattr(c, "text"))
            assert "msg-000001" in text and "NDA review" in text
