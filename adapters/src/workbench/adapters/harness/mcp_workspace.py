"""Live MCP sessions over a materialized workspace.

``open_workspace`` reads the workspace ``.mcp.json``, spawns every server
as a stdio subprocess with the workspace as its working directory (db
paths in the config are workspace-relative), and exposes the union of
their tools under namespaced names (``{server}__{tool}``) in OpenAI
function format. Tool failures come back as ``"ERROR: ..."`` strings, so
the episode loop can hand them to the model instead of dying.
"""

import json
import sys
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import Any

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

TOOL_SEPARATOR = "__"


def _resolve_command(command: str) -> str:
    # Workspace configs name the in-container interpreter; on the host the
    # serving interpreter is this venv's own.
    if command in ("python3", "python"):
        return sys.executable
    return command


class McpWorkspace:
    """The open tool surface of one workspace; construct via open_workspace."""

    def __init__(self) -> None:
        self._sessions: dict[str, ClientSession] = {}
        self._specs: list[dict[str, Any]] = []

    def tool_specs(self) -> list[dict[str, Any]]:
        """Every server tool as an OpenAI function spec, namespaced."""
        return list(self._specs)

    async def call(self, namespaced_name: str, arguments: dict[str, Any]) -> str:
        """Call ``{server}__{tool}``; failures return an ``ERROR:`` string."""
        server, _, tool = namespaced_name.partition(TOOL_SEPARATOR)
        session = self._sessions.get(server)
        if session is None or not tool:
            return f"ERROR: unknown tool {namespaced_name!r}"
        try:
            result = await session.call_tool(tool, arguments)
        except Exception as error:
            return f"ERROR: {error}"
        text = "".join(block.text for block in result.content if hasattr(block, "text"))
        if getattr(result, "is_error", False):
            return f"ERROR: {text or 'tool call failed'}"
        return text


@asynccontextmanager
async def open_workspace(workspace_dir: Path) -> AsyncIterator[McpWorkspace]:
    config = json.loads((workspace_dir / ".mcp.json").read_text(encoding="utf-8"))
    workspace = McpWorkspace()
    async with AsyncExitStack() as stack:
        for server_name in sorted(config["mcpServers"]):
            spec = config["mcpServers"][server_name]
            parameters = StdioServerParameters(
                command=_resolve_command(spec["command"]),
                args=list(spec["args"]),
                cwd=str(workspace_dir),
            )
            read, write = await stack.enter_async_context(stdio_client(parameters))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            listing = await session.list_tools()
            workspace._sessions[server_name] = session
            for tool in listing.tools:
                workspace._specs.append(
                    {
                        "type": "function",
                        "function": {
                            "name": f"{server_name}{TOOL_SEPARATOR}{tool.name}",
                            "description": tool.description or "",
                            "parameters": tool.input_schema,
                        },
                    }
                )
        yield workspace
