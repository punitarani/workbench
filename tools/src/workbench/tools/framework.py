"""The tool-system contract and the shared surfaces every system carries.

A tool system is data: a name, the world-log tags it may observe, its
tables, and two functions — project events into a connection, and register
read tools on a server. The constructor enforces the offstage boundary
structurally: a system that declares a ``sim.*`` tag cannot exist. The
shared people table, the shared meta table (the log's onstage calendar
epoch), and the ``directory`` tool live here so every database answers
"who works here" and "when is now" the same way.
"""

import sqlite3
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Annotated

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
    return datetime.fromisoformat(entries[0].value)


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
    # Only the epoch string leaves the run.started payload: it is onstage
    # calendar reality. Everything else in it stays offstage.
    for event in events:
        if isinstance(event.payload, SimRunStartedPayload):
            yield MetaEntry(key="epoch", value=event.payload.epoch)
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
    server = MCPServer(
        name=f"workbench-{system.name}",
        instructions=f"The organization's {system.name} system.",
    )
    system.register(server, db_path)
    if system.directory_tool:
        _add_directory(server, db_path)
    return server


def _add_directory(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def directory() -> list[dict]:
        """List everyone in the organization's directory."""
        with connect_readonly(db_path) as connection:
            people = PEOPLE_TABLE.select(connection, order_by="person_id")
        return [person.model_dump() for person in people]
