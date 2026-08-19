"""Cross-database coherence: every reference in any projected database must
resolve. References are declared on the row models (``Id``/``Ref`` column
markers), so this walk needs no per-tool code. Coherence is inherited from
the single world log; this check proves the projections preserved it."""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from tools.db import connect_readonly
from tools.framework import ToolSystem


class CoherenceFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    database: str
    detail: str


def _present(connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def check_coherence(
    state_dir: Path, systems: Sequence[ToolSystem]
) -> tuple[CoherenceFinding, ...]:
    connections = {
        system.name: connect_readonly(state_dir / f"{system.name}.db")
        for system in systems
    }
    try:
        known: dict[str, set[str]] = {}
        for system in systems:
            connection = connections[system.name]
            for table in system.all_tables():
                if not _present(connection, table.name):
                    # A workspace materialized before a system grew an action
                    # table simply has no rows there, and no rows can dangle.
                    continue
                for column, marker in table.ids().items():
                    values = connection.execute(f"SELECT {column} FROM {table.name}")
                    known.setdefault(marker.kind, set()).update(
                        row[0] for row in values if row[0] is not None
                    )

        findings: list[CoherenceFinding] = []
        for system in systems:
            connection = connections[system.name]
            for table in system.all_tables():
                if not _present(connection, table.name):
                    continue
                for column, marker in table.refs().items():
                    values = {
                        row[0]
                        for row in connection.execute(
                            f"SELECT DISTINCT {column} FROM {table.name}"
                        )
                        if row[0] is not None
                    }
                    for value in sorted(values - known.get(marker.kind, set())):
                        findings.append(
                            CoherenceFinding(
                                database=system.name,
                                detail=(
                                    f"{table.name}.{column} references unknown "
                                    f"{marker.kind} {value}"
                                ),
                            )
                        )
    finally:
        for connection in connections.values():
            connection.close()

    return tuple(findings)
