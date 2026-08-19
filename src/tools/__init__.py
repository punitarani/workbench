"""Agent-facing tool systems: projections from the world log into per-tool
SQLite databases, and read-only MCP servers over them.

Each system is a subpackage implementing the ``ToolSystem`` contract; the
registry drives everything else. The offstage boundary holds structurally:
only the tags a system declares in ``handled_tags`` can reach its database,
and a system that declares ``sim.*`` cannot be constructed.
"""

from tools.registry import (
    REGISTRY,
    build_server,
    check_coherence,
    get_system,
    project_all,
    server_specs,
)

__all__ = [
    "REGISTRY",
    "build_server",
    "check_coherence",
    "get_system",
    "project_all",
    "server_specs",
]
