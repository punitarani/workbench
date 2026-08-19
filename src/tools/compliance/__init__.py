"""Compliance: the one write surface, for agentic intake-workflow tasks.

Unlike the product systems, this database is not projected from the world log —
its reference tables are *seeded from a scenario* (the discoverable conflict
traps that have no home on the Clio/Gmail surfaces), and its action tables start
empty and are written by the agent's tools as it completes the intake. Grading
reads the action tables against an expected end-state, at pass^k.

``project`` is therefore a no-op over world-log events (people and the calendar
epoch still populate through the shared framework path); ``seed`` fills the
reference tables at task-build time.
"""

import json
import sqlite3
from collections.abc import Sequence
from pathlib import Path

from core.events import Event
from tools.compliance.server import register
from tools.compliance.tables import (
    ADVANCE_WAIVERS,
    ALL_TABLES,
    ENTITY_OWNERSHIP,
    EXISTING_REPRESENTATIONS,
    FIRM_POSITIONS,
    LATERALS,
    PROSPECTIVE_CLIENTS,
    AdvanceWaiver,
    EntityOwnership,
    ExistingRepresentation,
    FirmPosition,
    Lateral,
    ProspectiveClient,
)
from tools.framework import ToolSystem

_SEED_TABLES = {
    "firm_positions": (FIRM_POSITIONS, FirmPosition),
    "prospective_clients": (PROSPECTIVE_CLIENTS, ProspectiveClient),
    "laterals": (LATERALS, Lateral),
    "advance_waivers": (ADVANCE_WAIVERS, AdvanceWaiver),
    "entity_ownership": (ENTITY_OWNERSHIP, EntityOwnership),
    "existing_representations": (EXISTING_REPRESENTATIONS, ExistingRepresentation),
}


def _project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    # No projection from the world log: reference tables are scenario-seeded,
    # action tables are agent-written. People/meta come from the shared path.
    return None


def seed(connection: sqlite3.Connection, scenario: dict[str, list[dict]]) -> None:
    """Insert a scenario's reference rows. ``scenario`` maps each reference
    table name to a list of row dicts; unknown keys are rejected so a typo in a
    fixture is a build failure, not a silently empty trap."""
    for key, rows in scenario.items():
        if key not in _SEED_TABLES:
            raise KeyError(f"compliance scenario has no reference table {key!r}")
        table, model = _SEED_TABLES[key]
        table.insert(connection, [model.model_validate(row) for row in rows])
    connection.commit()


SYSTEM = ToolSystem(
    name="compliance",
    handled_tags=("person.record",),
    tables=ALL_TABLES,
    project=_project,
    register=register,
    directory_tool=False,
)


def build_state(db_path: Path, scenario_path: Path) -> Path:
    """Create ``compliance.db`` for a task bundle and seed its reference tables
    from ``scenario_path``. The action tables start empty; the agent writes them
    at run time and the verifier grades the result. Called at task-build time
    (build_tasks.py) — this system is not world-log-projected like the read-only
    surfaces, so it is materialized here instead of in ``project_all``."""
    from tools.db import create_db

    connection = create_db(db_path, SYSTEM.all_tables())
    try:
        seed(connection, json.loads(Path(scenario_path).read_text()))
    finally:
        connection.close()
    return db_path
