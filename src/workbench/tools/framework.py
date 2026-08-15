"""The tool-system contract and the shared surfaces every system carries.

A tool system is data: a name, the world-log tags it may observe, its
tables, and two functions — project events into a connection, and register
read tools on a server. The constructor enforces the offstage boundary
structurally: a system that declares a ``sim.*`` tag cannot exist. The
shared people table, the shared meta table (the log's onstage calendar
epoch), and the ``directory`` tool live here so every database answers
"who works here" and "when is now" the same way.
"""

import os
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.core.errors import WorkbenchError
from workbench.core.events import Event
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.people import PersonRecordPayload
from workbench.tools.db import Id, Table, connect_readonly, create_db


class ToolContractError(WorkbenchError):
    """A tool system violates the plugin contract."""


class UnknownRefError(WorkbenchError):
    """A tool was asked about an id that does not exist."""


class SeatUnsetError(WorkbenchError):
    """A tool needs the active seat, but this server was started without one."""


def seat() -> str | None:
    """The person_id this server presents, or None for an org-wide server.

    Read per call rather than at import time, so a test or a process that
    changes seats mid-flight sees the change.
    """

    return os.environ.get("WORKBENCH_SEAT")


def require_seat(tool: str) -> str:
    person = seat()
    if person is None:
        raise SeatUnsetError(
            f"{tool} needs an active seat: start the server with --user, or set "
            "WORKBENCH_SEAT to the person_id whose account this server presents"
        )
    return person


class Person(BaseModel):
    person_id: Annotated[str, Id("person")]
    name: str
    email_address: str
    title: str
    department: str
    affiliation: str


PEOPLE_TABLE = Table("people", Person, primary_key=("person_id",))


class MetaEntry(BaseModel):
    key: str
    value: str


META_TABLE = Table("meta", MetaEntry, primary_key=("key",))


def read_epoch(connection: sqlite3.Connection) -> datetime:
    """The calendar moment of simulated time zero, from the meta table.

    Every served date derives from this: a record at time ``t`` happened
    at ``epoch + timedelta(seconds=t)``.
    """

    entries = META_TABLE.select(connection, where={"key": "epoch"})
    if not entries:
        raise ToolContractError(
            "database carries no epoch; it was not projected from a world log"
        )
    epoch = datetime.fromisoformat(entries[0].value)
    timezone_entries = META_TABLE.select(connection, where={"key": "timezone"})
    if not timezone_entries:
        return epoch
    try:
        timezone = ZoneInfo(timezone_entries[0].value)
    except ZoneInfoNotFoundError as error:
        raise ToolContractError("database carries an unknown timezone") from error
    zoned_epoch = epoch.replace(tzinfo=timezone)
    if epoch.utcoffset() is None or epoch.utcoffset() != zoned_epoch.utcoffset():
        raise ToolContractError(
            "database epoch offset does not match its calendar timezone"
        )
    return zoned_epoch


type Projector = Callable[[Sequence[Event], sqlite3.Connection], None]
type Registrar = Callable[[MCPServer, Path], None]


@dataclass(frozen=True, slots=True)
class ToolSystem:
    name: str
    handled_tags: tuple[str, ...]
    tables: tuple[Table, ...]
    project: Projector
    register: Registrar
    # Product-realistic systems expose people through their own surfaces
    # (Slack user tools, Clio users, iManage user info) instead of the
    # generic directory tool.
    directory_tool: bool = True

    def __post_init__(self) -> None:
        offstage = [tag for tag in self.handled_tags if tag.startswith("sim.")]
        if offstage:
            raise ToolContractError(
                f"{self.name}: sim.* events are offstage and never reach a "
                f"tool database: {offstage}"
            )
        if "person.record" not in self.handled_tags:
            raise ToolContractError(
                f"{self.name}: every database carries the shared people table; "
                "declare person.record in handled_tags"
            )
        if not self.tables:
            raise ToolContractError(f"{self.name}: a tool system declares its tables")
        names = [table.name for table in self.tables]
        shared = {PEOPLE_TABLE.name, META_TABLE.name}
        if len(set(names)) != len(names) or shared & set(names):
            raise ToolContractError(f"{self.name}: table names collide: {names}")

    def all_tables(self) -> tuple[Table, ...]:
        return (META_TABLE, PEOPLE_TABLE, *self.tables)


def _people(events: Sequence[Event]) -> Iterator[Person]:
    for event in events:
        payload = event.payload
        if isinstance(payload, PersonRecordPayload):
            yield Person(
                person_id=payload.person_id,
                name=payload.name,
                email_address=payload.email_address,
                title=payload.title,
                department=payload.department,
                affiliation=payload.affiliation,
            )


def _meta(events: Sequence[Event]) -> Iterator[MetaEntry]:
    # Calendar origin and timezone are onstage reality. Run identity,
    # configuration, and seed remain offstage.
    for event in events:
        if isinstance(event.payload, SimRunStartedPayload):
            yield MetaEntry(key="epoch", value=event.payload.epoch)
            yield MetaEntry(key="timezone", value=event.payload.timezone)
            return


def project_system(system: ToolSystem, events: Sequence[Event], db_path: Path) -> None:
    connection = create_db(db_path, system.all_tables())
    try:
        with connection:
            META_TABLE.insert(connection, _meta(events))
            PEOPLE_TABLE.insert(connection, _people(events))
            system.project(events, connection)
    finally:
        connection.close()


def build_server(system: ToolSystem, db_path: Path) -> MCPServer:
    _ensure_tables(system, db_path)
    server = MCPServer(
        name=f"workbench-{system.name}",
        instructions=f"The organization's {system.name} system.",
    )
    system.register(server, db_path)
    if system.directory_tool:
        _add_directory(server, db_path)
    return server


def _ensure_tables(system: ToolSystem, db_path: Path) -> None:
    """Create any declared table the database is missing.

    A workspace materialized before a system grew an action table would
    otherwise fail every read that touches it — and those failures land in
    task bundles built months earlier, far from the change that caused
    them. The server owns this file and knows its own schema, so it
    reconciles rather than crashing. Projected tables are always created by
    ``project_system``, so this only ever fills in empty action tables.
    """

    if not db_path.exists():
        return
    connection = sqlite3.connect(db_path)
    try:
        with connection:
            for table in system.all_tables():
                connection.execute(
                    table.ddl().replace("CREATE TABLE", "CREATE TABLE IF NOT EXISTS")
                )
    finally:
        connection.close()


def _add_directory(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def directory() -> list[dict]:
        """List everyone in the organization's directory."""
        with connect_readonly(db_path) as connection:
            people = PEOPLE_TABLE.select(connection, order_by="person_id")
        return [person.model_dump() for person in people]
