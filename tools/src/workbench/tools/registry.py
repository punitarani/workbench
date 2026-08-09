"""Every tool system, one line each.

The registry drives projection, coherence checking, server assembly,
bundle ``mcp.json`` specs, and the serve entry point: adding a system
is one subpackage implementing the contract and one line here.
"""

from collections.abc import Sequence
from pathlib import Path

from mcp.server import MCPServer

from workbench.core.errors import WorkbenchError
from workbench.core.events import Event
from workbench.tools import clio, coherence, framework, gmail, imanage, slack
from workbench.tools.framework import ToolSystem

REGISTRY: tuple[ToolSystem, ...] = (
    gmail.SYSTEM,
    slack.SYSTEM,
    imanage.SYSTEM,
    clio.SYSTEM,
)


def get_system(name: str) -> ToolSystem:
    for system in REGISTRY:
        if system.name == name:
            return system
    raise WorkbenchError(f"unknown tool {name!r}")


def project_all(events: Sequence[Event], out_dir: Path) -> dict[str, Path]:
    """Project a world log into one database per system. Returns the paths."""
    events = list(events)
    paths: dict[str, Path] = {}
    for system in REGISTRY:
        db_path = out_dir / f"{system.name}.db"
        framework.project_system(system, events, db_path)
        paths[system.name] = db_path
    return paths


def build_server(tool_name: str, db_path: Path) -> MCPServer:
    return framework.build_server(get_system(tool_name), db_path)


def check_coherence(state_dir: Path) -> tuple[coherence.CoherenceFinding, ...]:
    return coherence.check_coherence(state_dir, REGISTRY)


def server_specs(seat: str | None = None) -> dict[str, dict[str, object]]:
    """Launch specs for a bundle ``mcp.json``; db paths are bundle-relative."""
    seat_args = ["--user", seat] if seat else []
    return {
        system.name: {
            "command": "python3",
            "args": [
                "-m",
                "workbench.tools.serve",
                system.name,
                "--db",
                f"state/{system.name}.db",
                *seat_args,
            ],
        }
        for system in sorted(REGISTRY, key=lambda system: system.name)
    }
