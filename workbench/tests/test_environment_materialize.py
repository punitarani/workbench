"""Environment assembly: world log in, agent-inhabitable workspace out."""

import json
import sys
import tomllib
from pathlib import Path

import pytest
from worldlog_fixtures import coherent_events

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.worldlog import WorldLogWriter
from workbench.environment import materialize
from workbench.tools.coherence import check_coherence


def write_log(tmp_path: Path) -> Path:
    log_path = tmp_path / "world.jsonl"
    with WorldLogWriter(log_path) as writer:
        for event in coherent_events():
            writer.append(event)
    return log_path


def test_materialize_produces_workspace(tmp_path: Path) -> None:
    log_path = write_log(tmp_path)
    out = tmp_path / "workspace"
    result = materialize(log_path, out)

    assert sorted(p.name for p in (out / "state").iterdir()) == [
        "chat.db",
        "dms.db",
        "mail.db",
        "matters.db",
    ]
    assert check_coherence(out / "state") == ()

    config = json.loads((out / ".mcp.json").read_text())
    servers = config["mcpServers"]
    assert set(servers) == {"mail", "chat", "dms", "matters"}
    for name, spec in servers.items():
        assert spec["args"][-2:] == ["--db", f"state/{name}.db"]

    environment = tomllib.loads((out / "environment.toml").read_text())
    assert set(environment["tools"]["compose"]) == {"mail", "chat", "dms", "matters"}
    assert result.event_count == len(coherent_events())


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
    out = tmp_path / "workspace"
    materialize(log_path, out)

    parameters = StdioServerParameters(
        command=sys.executable,
        args=["-m", "workbench.tools.serve", "mail", "--db", "state/mail.db"],
        cwd=str(out),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {t.name for t in tools.tools}
            assert {"list_threads", "read_thread", "search_mail", "directory"} <= names
            result = await session.call_tool("read_thread", {"thread_id": "thr-000001"})
            text = "".join(c.text for c in result.content if hasattr(c, "text"))
            assert "msg-000001" in text and "NDA review" in text
