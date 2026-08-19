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

from core.errors import WorldLogIntegrityError
from core.events.documents import DocumentCreatedPayload
from core.worldlog import read_events, validate_events
from tools import REGISTRY, project_all, server_specs

AGENT_WORKSPACE = "workspace"


class MaterializedEnvironment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    bundle: Path
    agent_workspace: Path
    event_count: int = Field(ge=0)
    databases: tuple[str, ...]
    seat: str | None = None
    document_files: int = Field(ge=0, default=0)
    # Renders that fell back (e.g. PDF without soffice installed) — recorded,
    # never silently swallowed.
    skipped_renders: tuple[str, ...] = ()


def _write_document_files(
    agent_workspace: Path, imanage_db: Path, formats: dict[str, str]
) -> tuple[int, tuple[str, ...]]:
    """Every document's head version becomes a real file in the agent's own
    folders, laid out as ``{workspace}/{basename}`` from the iManage
    profile — the way a professional's documents sit on disk. Structured
    content renders into real office files; rendered bytes are derived
    artifacts, so determinism never depends on them."""

    connection = sqlite3.connect(imanage_db)
    try:
        rows = connection.execute(
            "SELECT documents.document_id, documents.workspace, "
            "documents.path, versions.content, documents.extension "
            "FROM documents JOIN versions "
            "ON versions.document_id = documents.document_id "
            "AND versions.version = documents.head_version "
            "ORDER BY documents.document_number"
        ).fetchall()
    finally:
        connection.close()
    skipped: list[str] = []
    for document_id, workspace, path, content, extension in rows:
        # The name follows the bytes. An author who declared a workbook and
        # named it `.docx` would otherwise leave a file Word cannot open,
        # and an agent that trusts the extension is misled by the
        # environment rather than by the work.
        basename = path.rsplit("/", 1)[-1]
        stem = basename.rsplit(".", 1)[0] if "." in basename else basename
        target = agent_workspace / workspace / f"{stem}.{extension}"
        content_format = formats.get(document_id, "markdown")
        if content_format == "markdown":
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            continue
        # Lazy import: rendering needs the ``artifacts`` extra, which the
        # base install (markdown-only worlds) does not carry.
        from artifacts.render import render_document

        outcome = render_document(content_format, content, target)
        if outcome.skipped is not None:
            skipped.append(outcome.skipped)
    return len(rows), tuple(skipped)


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
    formats = {
        event.payload.document_id: event.payload.content_format
        for event in events
        if isinstance(event.payload, DocumentCreatedPayload)
    }
    document_files, skipped_renders = _write_document_files(
        agent_workspace, databases["imanage"], formats
    )

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
        skipped_renders=skipped_renders,
    )
