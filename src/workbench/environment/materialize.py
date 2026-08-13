"""Materialize a world log into an environment bundle.

Validation is a gate, not a warning: an incoherent log never becomes an
environment. The bundle splits what the agent inhabits from what serves
it: only ``workspace/`` becomes ``/home/agent/workspace``, while
``state/`` (the projected tool databases), ``mcp.json``, and
``environment.toml`` stay offstage under the bundle root, readable by the
environment user alone. The emulated products are therefore the only
route into the record. Server commands in ``mcp.json`` are bundle-relative
and the container wraps them with run-as-environment.
"""

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.worldlog import read_events, validate_events
from workbench.tools import REGISTRY, project_all, server_specs

AGENT_WORKSPACE = "workspace"


class MaterializedEnvironment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle: Path
    agent_workspace: Path
    event_count: int = Field(ge=0)
    databases: tuple[str, ...]
    seat: str | None = None
    document_files: int = Field(ge=0, default=0)


def _write_document_files(agent_workspace: Path, imanage_db: Path) -> int:
    """Every document's head version becomes a real file in the agent's own
    folders, laid out as ``{workspace}/{basename}`` from the iManage
    profile — the way a professional's documents sit on disk."""

    connection = sqlite3.connect(imanage_db)
    try:
        rows = connection.execute(
            "SELECT documents.workspace, documents.path, versions.content "
            "FROM documents JOIN versions "
            "ON versions.document_id = documents.document_id "
            "AND versions.version = documents.head_version "
            "ORDER BY documents.document_number"
        ).fetchall()
    finally:
        connection.close()
    for workspace, path, content in rows:
        target = agent_workspace / workspace / path.rsplit("/", 1)[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return len(rows)


def materialize(
    world_log: Path, out_dir: Path, *, seat: str | None = None
) -> MaterializedEnvironment:
    """Write the environment bundle rooted at ``out_dir``. The bundle root
    is never the agent's working directory; ``out_dir/workspace`` is."""

    events = read_events(world_log)
    report = validate_events(events)
    if not report.ok:
        details = "; ".join(
            f"seq {f.seq} {f.code}: {f.detail}" for f in report.findings[:5]
        )
        raise WorldLogIntegrityError(
            f"refusing to materialize an incoherent log: {details}"
        )

    out_dir.mkdir(parents=True, exist_ok=True)
    agent_workspace = out_dir / AGENT_WORKSPACE
    agent_workspace.mkdir(parents=True, exist_ok=True)
    databases = project_all(events, out_dir / "state")
    document_files = _write_document_files(agent_workspace, databases["imanage"])

    (out_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": server_specs(seat=seat)}, indent=2) + "\n",
        encoding="utf-8",
    )

    names = sorted(system.name for system in REGISTRY)
    compose = ", ".join(f'"{name}"' for name in names)
    seat_line = f'seat = "{seat}"\n' if seat else ""
    (out_dir / "environment.toml").write_text(
        f"[tools]\ncompose = [{compose}]\n{seat_line}"
        f'\n[agent]\nworkspace = "{AGENT_WORKSPACE}"\n'
        '\n[personas]\nbackend = "replay"\n',
        encoding="utf-8",
    )

    return MaterializedEnvironment(
        bundle=out_dir,
        agent_workspace=agent_workspace,
        event_count=len(events),
        databases=tuple(names),
        seat=seat,
        document_files=document_files,
    )
