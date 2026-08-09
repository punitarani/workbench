"""Agent-facing tool systems: projections from the world log into per-tool
SQLite databases, and (in the container) the MCP servers over them.

The offstage boundary holds structurally: only the tags a projector declares
in ``handled_tags`` can reach its database, and no projector handles ``sim.*``.
"""

from collections.abc import Sequence
from pathlib import Path

from workbench.core.events import Event
from workbench.tools import chat, dms, mail, matters

PROJECTORS = {
    "mail": mail,
    "chat": chat,
    "dms": dms,
    "matters": matters,
}


def project_all(events: Sequence[Event], out_dir: Path) -> dict[str, Path]:
    """Project a world log into one database per tool. Returns the paths."""
    events = list(events)
    paths: dict[str, Path] = {}
    for name, projector in PROJECTORS.items():
        db_path = out_dir / f"{name}.db"
        projector.project(events, db_path)
        paths[name] = db_path
    return paths
