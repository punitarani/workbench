"""MCP-shaped read tools mirroring the Clio Manage API v4.

No official Clio MCP exists; these tools mirror the v4 REST resources
(matters, contacts, activities, notes, users) with Clio's field names,
integer ids, and the ``{"data": ...}`` response envelope. Integer id
spaces derive deterministically from the projected tables: matters are
numbered in creation order, contacts are organizations (by org id) then
external people (by person id), users are internal people (by person id).
"""

import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer
from pydantic import BaseModel

from workbench.tools.clio.tables import (
    ACTIVITIES,
    MATTERS,
    NOTES,
    ORGANIZATIONS,
    Matter,
    clio_status,
)
from workbench.tools.db import Query, connect_readonly
from workbench.tools.framework import (
    PEOPLE_TABLE,
    Person,
    UnknownRefError,
    read_epoch,
    require_seat,
)

# Clio's licence split: everyone who practises law holds an Attorney seat.
# "associate" is as much a practising title as "partner" or "counsel".
ATTORNEY_TITLE_WORDS = ("counsel", "attorney", "partner", "associate")


def _iso_date(directory: _Directory, time: int) -> str:
    return (directory.epoch + timedelta(seconds=time)).date().isoformat()


class PracticeArea(BaseModel):
    name: str


class PartyStub(BaseModel):
    id: int
    name: str


class ClientStub(PartyStub):
    type: str = "Company"


class MatterStub(BaseModel):
    id: int
    display_number: str


class MatterRecord(BaseModel):
    id: int
    etag: str
    number: int
    display_number: str
    # Clio v4 gives a matter one free-text field for what it is about —
    # `description` — and identifies it by `display_number`. The workplace
    # record carries both a one-line title and a substantive description, so
    # `description` takes the substantive text (Clio's own meaning for the
    # field) and the one-liner stays reachable as `title`, which Clio has no
    # field of its own for.
    title: str
    description: str
    status: str
    open_date: str
    close_date: str | None
    practice_area: PracticeArea
    client: ClientStub | None
    responsible_attorney: PartyStub | None
    originating_attorney: PartyStub


class MatterDetail(MatterRecord):
    notes_count: int
    activities_count: int


class ContactRecord(BaseModel):
    id: int
    etag: str
    name: str
    type: Literal["Company", "Person"]
    is_client: bool
    primary_email_address: str | None


class MatterContactRecord(BaseModel):
    id: int
    name: str
    type: Literal["Company", "Person"]
    is_client: bool
    relationship_name: str


class ActivityRecord(BaseModel):
    id: int
    etag: str
    type: str = "TimeEntry"
    date: str
    quantity: int
    quantity_in_hours: float
    note: str
    matter: MatterStub
    user: PartyStub


class NoteRecord(BaseModel):
    id: int
    type: str = "Matter"
    subject: str
    detail: str
    date: str
    matter: MatterStub
    author: PartyStub


class UserRecord(BaseModel):
    id: int
    etag: str
    name: str
    first_name: str
    last_name: str
    email: str
    enabled: bool
    subscription_type: Literal["Attorney", "NonAttorney"]


class _StatusChange(BaseModel):
    ticket_id: str
    new_value: str | None
    time: int


STATUS_CHANGES = Query(
    _StatusChange,
    "SELECT ticket_id, new_value, time FROM matter_history "
    "WHERE field='status' ORDER BY time",
)


class _Directory:
    """Clio's integer id spaces, derived from the projected tables."""

    def __init__(self, connection: sqlite3.Connection) -> None:
        self.organizations = ORGANIZATIONS.select(connection, order_by="org_id")
        people = PEOPLE_TABLE.select(connection, order_by="person_id")
        self.users = [p for p in people if p.affiliation == "internal"]
        self.external = [p for p in people if p.affiliation == "external"]
        self.contact_ids = {o.org_id: n for n, o in enumerate(self.organizations, 1)}
        offset = len(self.organizations)
        self.contact_ids.update(
            {p.person_id: offset + n for n, p in enumerate(self.external, 1)}
        )
        self.user_ids = {p.person_id: n for n, p in enumerate(self.users, 1)}
        self.people = {p.person_id: p for p in people}
        self.org_names = {o.org_id: o.name for o in self.organizations}
        self.epoch = read_epoch(connection)

    def party(self, person_id: str) -> PartyStub:
        number = self.user_ids.get(person_id) or self.contact_ids[person_id]
        return PartyStub(id=number, name=self.people[person_id].name)

    def client(self, org_id: str | None) -> ClientStub | None:
        if org_id is None:
            return None
        return ClientStub(id=self.contact_ids[org_id], name=self.org_names[org_id])


def _close_times(connection: sqlite3.Connection) -> dict[str, int]:
    closes: dict[str, int] = {}
    for change in STATUS_CHANGES.run(connection):
        if change.new_value is not None and clio_status(change.new_value) == "Closed":
            closes[change.ticket_id] = change.time
        else:
            closes.pop(change.ticket_id, None)
    return closes


def _matter_record(
    matter: Matter, directory: _Directory, closes: dict[str, int]
) -> MatterRecord:
    close_time = closes.get(matter.ticket_id)
    return MatterRecord(
        id=matter.matter_number,
        etag=f'"m{matter.matter_number}"',
        number=matter.matter_number,
        display_number=matter.display_number,
        title=matter.description,
        description=matter.detail,
        status=matter.status,
        open_date=_iso_date(directory, matter.open_time),
        close_date=None if close_time is None else _iso_date(directory, close_time),
        practice_area=PracticeArea(name=matter.practice_area),
        client=directory.client(matter.client_org),
        responsible_attorney=(
            None
            if matter.responsible_person is None
            else directory.party(matter.responsible_person)
        ),
        originating_attorney=directory.party(matter.originating_person),
    )


def _user_record(directory: _Directory, person: Person) -> UserRecord:
    parts = person.name.split()
    number = directory.user_ids[person.person_id]
    attorney = any(word in person.title.lower() for word in ATTORNEY_TITLE_WORDS)
    return UserRecord(
        id=number,
        etag=f'"u{number}"',
        name=person.name,
        first_name=parts[0],
        last_name=parts[-1] if len(parts) > 1 else "",
        email=person.email_address,
        enabled=True,
        subscription_type="Attorney" if attorney else "NonAttorney",
    )


def _matter_by_number(connection: sqlite3.Connection, number: int) -> Matter:
    matters = MATTERS.select(connection, where={"matter_number": number})
    if not matters:
        raise UnknownRefError(f"no matter {number}")
    return matters[0]


def _page(records: list) -> dict:
    return {"data": [r.model_dump() for r in records], "meta": {"paging": {}}}


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_matters(
        status: str | None = None,
        query: str | None = None,
        client_id: int | None = None,
        limit: int = 200,
    ) -> dict:
        """List matters; filter by status (open/closed/pending), a wildcard
        query over display number, title, description, and client name, or a
        client contact id."""
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
            closes = _close_times(connection)
            records = [
                _matter_record(m, directory, closes)
                for m in MATTERS.select(connection, order_by="matter_number")
            ]
        if status is not None:
            records = [r for r in records if r.status.lower() == status.lower()]
        if query is not None:
            needle = query.lower()
            records = [
                r
                for r in records
                if needle in r.display_number.lower()
                or needle in r.title.lower()
                or needle in r.description.lower()
                or (r.client is not None and needle in r.client.name.lower())
            ]
        if client_id is not None:
            records = [
                r for r in records if r.client is not None and r.client.id == client_id
            ]
        return _page(records[:limit])

    @server.tool()
    def get_matter(id: int) -> dict:
        """Read one matter, with its notes and activities counts."""
        with connect_readonly(db_path) as connection:
            matter = _matter_by_number(connection, id)
            record = _matter_record(
                matter, _Directory(connection), _close_times(connection)
            )
            detail = MatterDetail(
                **record.model_dump(),
                notes_count=len(
                    NOTES.select(connection, where={"ticket_id": matter.ticket_id})
                ),
                activities_count=len(
                    ACTIVITIES.select(connection, where={"ticket_id": matter.ticket_id})
                ),
            )
        return {"data": detail.model_dump()}

    @server.tool()
    def list_matter_contacts(matter_id: int) -> dict:
        """List the contacts related to a matter: the client organization
        plus external participants."""
        with connect_readonly(db_path) as connection:
            matter = _matter_by_number(connection, matter_id)
            directory = _Directory(connection)
        records: list[MatterContactRecord] = []
        if matter.client_org is not None:
            records.append(
                MatterContactRecord(
                    id=directory.contact_ids[matter.client_org],
                    name=directory.org_names[matter.client_org],
                    type="Company",
                    is_client=True,
                    relationship_name="Client",
                )
            )
        requester = directory.people[matter.originating_person]
        if requester.affiliation == "external":
            records.append(
                MatterContactRecord(
                    id=directory.contact_ids[requester.person_id],
                    name=requester.name,
                    type="Person",
                    is_client=False,
                    relationship_name="Participant",
                )
            )
        return _page(records)

    @server.tool()
    def list_contacts(query: str | None = None, type: str | None = None) -> dict:
        """List contacts (organizations and outside people); filter by a
        wildcard name query or by type (Company/Person)."""
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
        records = [
            ContactRecord(
                id=directory.contact_ids[o.org_id],
                etag=f'"c{directory.contact_ids[o.org_id]}"',
                name=o.name,
                type="Company",
                is_client=o.category == "client",
                primary_email_address=None,
            )
            for o in directory.organizations
        ] + [
            ContactRecord(
                id=directory.contact_ids[p.person_id],
                etag=f'"c{directory.contact_ids[p.person_id]}"',
                name=p.name,
                type="Person",
                is_client=False,
                primary_email_address=p.email_address,
            )
            for p in directory.external
        ]
        if type is not None:
            records = [r for r in records if r.type.lower() == type.lower()]
        if query is not None:
            needle = query.lower()
            records = [r for r in records if needle in r.name.lower()]
        return _page(records)

    @server.tool()
    def list_activities(
        matter_id: int | None = None,
        user_id: int | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        """List time entries, optionally scoped to one matter or one user;
        quantities are in seconds. Pages of at most 50 records; walk long
        histories with offset."""
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
            matters = {m.ticket_id: m for m in MATTERS.select(connection)}
            activities = ACTIVITIES.select(connection, order_by="time")
        records = []
        for number, activity in enumerate(activities, 1):
            matter = matters[activity.ticket_id]
            records.append(
                ActivityRecord(
                    id=number,
                    etag=f'"a{number}"',
                    date=_iso_date(directory, activity.time),
                    quantity=activity.quantity_seconds,
                    quantity_in_hours=round(activity.quantity_seconds / 3600, 2),
                    note=activity.note,
                    matter=MatterStub(
                        id=matter.matter_number,
                        display_number=matter.display_number,
                    ),
                    user=directory.party(activity.person),
                )
            )
        if matter_id is not None:
            if not any(m.matter_number == matter_id for m in matters.values()):
                raise UnknownRefError(f"no matter {matter_id}")
            records = [r for r in records if r.matter.id == matter_id]
        if user_id is not None:
            if user_id not in directory.user_ids.values():
                raise UnknownRefError(f"no user {user_id}")
            records = [r for r in records if r.user.id == user_id]
        limit = max(1, min(limit, 50))
        offset = max(offset, 0)
        page = records[offset : offset + limit]
        paging: dict[str, int] = {"total_entries": len(records)}
        if offset + limit < len(records):
            paging["next_offset"] = offset + limit
        return {
            "data": [r.model_dump() for r in page],
            "meta": {"paging": paging},
        }

    @server.tool()
    def list_notes(matter_id: int | None = None) -> dict:
        """List matter notes, oldest first."""
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
            matters = {m.ticket_id: m for m in MATTERS.select(connection)}
            notes = NOTES.select(connection, order_by="time")
        records = []
        for number, note in enumerate(notes, 1):
            matter = matters[note.ticket_id]
            records.append(
                NoteRecord(
                    id=number,
                    subject=note.detail[:60],
                    detail=note.detail,
                    date=_iso_date(directory, note.time),
                    matter=MatterStub(
                        id=matter.matter_number,
                        display_number=matter.display_number,
                    ),
                    author=directory.party(note.author),
                )
            )
        if matter_id is not None:
            if not any(m.matter_number == matter_id for m in matters.values()):
                raise UnknownRefError(f"no matter {matter_id}")
            records = [r for r in records if r.matter.id == matter_id]
        return _page(records)

    @server.tool()
    def list_users(enabled: bool = True) -> dict:
        """List the firm's users."""
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
        records = [_user_record(directory, person) for person in directory.users]
        records = [r for r in records if r.enabled is enabled]
        return _page(records)

    @server.tool()
    def who_am_i() -> dict:
        """Identify the Clio user for the active seat. Errors when this
        server runs without one: an unseated server has no identity, and a
        guessed one silently misattributes every "my matters" answer."""
        seat = require_seat("who_am_i")
        with connect_readonly(db_path) as connection:
            directory = _Directory(connection)
        person = directory.people.get(seat)
        if person is None or person.person_id not in directory.user_ids:
            raise UnknownRefError(f"no user for seat {seat}")
        return {"data": _user_record(directory, person).model_dump()}
