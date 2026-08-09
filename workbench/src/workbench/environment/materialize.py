"""Materialize a world log into an agent-inhabitable workspace.

Validation is a gate, not a warning: an incoherent log never becomes an
environment. Server commands in .mcp.json are workspace-relative; the
container wraps them with run-as-environment.
"""

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.worldlog import read_events, validate_events
from workbench.tools import PROJECTORS, project_all


class MaterializedEnvironment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    workspace: Path
    event_count: int = Field(ge=0)
    databases: tuple[str, ...]


def materialize(world_log: Path, out_dir: Path) -> MaterializedEnvironment:
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
    project_all(events, out_dir / "state")

    servers = {
        name: {
            "command": "python3",
            "args": ["-m", "workbench.tools.serve", name, "--db", f"state/{name}.db"],
        }
        for name in sorted(PROJECTORS)
    }
    (out_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": servers}, indent=2) + "\n", encoding="utf-8"
    )

    compose = ", ".join(f'"{name}"' for name in sorted(PROJECTORS))
    (out_dir / "environment.toml").write_text(
        f'[tools]\ncompose = [{compose}]\n\n[personas]\nbackend = "replay"\n',
        encoding="utf-8",
    )

    return MaterializedEnvironment(
        workspace=out_dir,
        event_count=len(events),
        databases=tuple(sorted(PROJECTORS)),
    )
