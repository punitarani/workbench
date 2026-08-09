"""Materialize a world log into an agent-inhabitable workspace.

Validation is a gate, not a warning: an incoherent log never becomes an
environment. Server commands in .mcp.json are workspace-relative; the
container wraps them with run-as-environment.
"""

import json
import sqlite3
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.worldlog import read_events, validate_events
from workbench.tools import REGISTRY, project_all, server_specs


class MaterializedEnvironment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace: Path
    event_count: int = Field(ge=0)
    databases: tuple[str, ...]
    seat: str | None = None
    document_files: int = Field(ge=0, default=0)


def _write_document_files(out_dir: Path, imanage_db: Path) -> int:
    """Every document's head version becomes a real file the agent can open,
    laid out as ``files/{workspace}/{basename}`` from the iManage profile."""

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
        target = out_dir / "files" / workspace / path.rsplit("/", 1)[-1]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    return len(rows)


def materialize(
    world_log: Path, out_dir: Path, *, seat: str | None = None
) -> MaterializedEnvironment:
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
    databases = project_all(events, out_dir / "state")
    document_files = _write_document_files(out_dir, databases["imanage"])

    (out_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": server_specs(seat=seat)}, indent=2) + "\n",
        encoding="utf-8",
    )

    names = sorted(system.name for system in REGISTRY)
    compose = ", ".join(f'"{name}"' for name in names)
    seat_line = f'seat = "{seat}"\n' if seat else ""
    (out_dir / "environment.toml").write_text(
        f"[tools]\ncompose = [{compose}]\n{seat_line}"
        '\n[personas]\nbackend = "replay"\n',
        encoding="utf-8",
    )

    return MaterializedEnvironment(
        workspace=out_dir,
        event_count=len(events),
        databases=tuple(names),
        seat=seat,
        document_files=document_files,
    )
