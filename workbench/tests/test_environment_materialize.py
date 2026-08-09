"""Environment assembly: world log in, environment bundle out."""

import json
import sys
import tomllib
from pathlib import Path

import pytest
from worldlog_fixtures import coherent_events

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.worldlog import WorldLogWriter
from workbench.environment import materialize
from workbench.tools import check_coherence


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

    assert sorted(p.name for p in (out / "state").iterdir()) == [
        "clio.db",
        "gmail.db",
        "imanage.db",
        "slack.db",
    ]
    assert check_coherence(out / "state") == ()

    config = json.loads((out / "mcp.json").read_text())
    servers = config["mcpServers"]
    assert set(servers) == {"gmail", "slack", "imanage", "clio"}
    for name, spec in servers.items():
        assert spec["args"][3:5] == ["--db", f"state/{name}.db"]

    environment = tomllib.loads((out / "environment.toml").read_text())
    assert set(environment["tools"]["compose"]) == {"gmail", "slack", "imanage", "clio"}
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
    # and was revised to "v2"; the head version becomes a real file in the
    # agent's own folders.
    target = out / "workspace" / "legal" / "nda-playbook.md"
    assert target.read_text(encoding="utf-8") == "v2"
    assert result.document_files == 1
    assert [p.name for p in result.agent_workspace.iterdir()] == ["legal"]


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
        args=["-m", "workbench.tools.serve", "gmail", "--db", "state/gmail.db"],
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
