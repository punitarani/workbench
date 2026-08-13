"""Read tools over the calendar database, shaped like Google Calendar.

The surface mirrors the read half of Google's official Calendar MCP
server: ``list_events``, ``get_event``, and ``list_calendars``, with that
server's argument names (``calendarId``, ``startTime``, ``endTime``,
``fullText``, ``orderBy``, ``pageSize``, ``pageToken``) and the Calendar
API v3 response field names — ``id``, ``summary``, ``description``,
``status``, ``created``, ``updated``, ``start``/``end`` as
``{"dateTime": ...}``, ``organizer``, and ``attendees`` of
``{email, displayName, responseStatus}``.

Calendars are people: a calendar's id is that person's email address,
exactly as in Google Workspace, and ``list_calendars`` is the set of
people who appear on any event.

Seat scoping: ``WORKBENCH_SEAT`` names the person_id whose calendar is
``primary``, read at call time. A ``calendarId`` of ``primary`` (the
default) means that person; with no seat it means every calendar, so an
unseated server reads org-wide like the other systems. Naming a calendar
explicitly always works — colleagues' calendars are visible inside a
firm.

Times render from the shared meta table's epoch plus the event's
simulated seconds, so a workspace built on another epoch serves its own
dates.
"""

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from mcp.server import MCPServer

from workbench.tools.calendar.tables import (
    ATTENDEES,
    CALENDAR_EVENTS,
    Attendee,
    CalendarEvent,
)
from workbench.tools.db import connect_readonly
from workbench.tools.framework import (
    PEOPLE_TABLE,
    Person,
    UnknownRefError,
    read_epoch,
    seat,
)

_MAX_EVENTS = 250
_MAX_CALENDARS = 250
_PRIMARY = "primary"


@dataclass(frozen=True, slots=True)
class _Calendars:
    events: list[CalendarEvent]
    attendees: dict[str, list[Attendee]]
    people: dict[str, Person]
    epoch: datetime

    def resolve(self, calendar_id: str | None) -> str | None:
        """The person whose calendar this is, or None for every calendar."""
        if not calendar_id or calendar_id == _PRIMARY:
            return seat()
        needle = calendar_id.lower()
        for person_id, person in self.people.items():
            if needle in (person_id.lower(), person.email_address.lower()):
                return person_id
        raise UnknownRefError(f"no calendar {calendar_id}")

    def on_calendar(self, event: CalendarEvent, person_id: str | None) -> bool:
        if person_id is None:
            return True
        return person_id == event.organizer or any(
            attendee.person_id == person_id
            for attendee in self.attendees[event.calendar_event_id]
        )

    def moment(self, seconds: int) -> datetime:
        return self.epoch + timedelta(seconds=seconds)


def _load(connection: sqlite3.Connection) -> _Calendars:
    attendees: dict[str, list[Attendee]] = {}
    for attendee in ATTENDEES.select(connection, order_by="person_id"):
        attendees.setdefault(attendee.calendar_event_id, []).append(attendee)
    events = CALENDAR_EVENTS.select(connection, order_by="calendar_event_id")
    return _Calendars(
        events=events,
        attendees={event.calendar_event_id: [] for event in events} | attendees,
        people={
            p.person_id: p
            for p in PEOPLE_TABLE.select(connection, order_by="person_id")
        },
        epoch=read_epoch(connection),
    )


def _principal(person: Person) -> dict[str, str]:
    return {"email": person.email_address, "displayName": person.name}


def _event_json(calendars: _Calendars, event: CalendarEvent) -> dict:
    return {
        "id": event.calendar_event_id,
        "summary": event.summary,
        "description": event.description,
        "status": event.status,
        "created": calendars.moment(event.created).isoformat(),
        "updated": calendars.moment(event.updated).isoformat(),
        "start": {"dateTime": calendars.moment(event.start_time).isoformat()},
        "end": {"dateTime": calendars.moment(event.end_time).isoformat()},
        "organizer": _principal(calendars.people[event.organizer]),
        "attendees": [
            {
                **_principal(calendars.people[attendee.person_id]),
                "responseStatus": attendee.response_status,
            }
            for attendee in calendars.attendees[event.calendar_event_id]
        ],
        "eventType": "default",
    }


def _boundary(value: str, epoch: datetime) -> datetime:
    moment = datetime.fromisoformat(value)
    # A bare local timestamp means the workspace's own timezone.
    return moment if moment.tzinfo else moment.replace(tzinfo=epoch.tzinfo)


def _matches_text(calendars: _Calendars, event: CalendarEvent, needle: str) -> bool:
    """Google's fullText spans the event and the people on it."""
    involved = {event.organizer} | {
        attendee.person_id for attendee in calendars.attendees[event.calendar_event_id]
    }
    haystacks = [event.summary, event.description]
    for person_id in involved:
        person = calendars.people[person_id]
        haystacks += [person.name, person.email_address]
    return any(needle in haystack.lower() for haystack in haystacks)


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_events(
        calendarId: str | None = None,
        startTime: str | None = None,
        endTime: str | None = None,
        fullText: str | None = None,
        orderBy: Literal["startTime", "updated"] = "startTime",
        pageSize: int = _MAX_EVENTS,
        pageToken: str | None = None,
    ) -> dict:
        """List calendar events. calendarId is an attendee's email address
        (or "primary", the default, for this seat's own calendar);
        startTime/endTime are ISO-8601 bounds keeping events that overlap
        the window; fullText matches the summary, description, and attendee
        names. At most 250 events per call — page with pageToken."""
        with connect_readonly(db_path) as connection:
            calendars = _load(connection)
        person_id = calendars.resolve(calendarId)
        after = None if startTime is None else _boundary(startTime, calendars.epoch)
        before = None if endTime is None else _boundary(endTime, calendars.epoch)
        needle = None if fullText is None else fullText.lower()
        matched = [
            event
            for event in calendars.events
            if calendars.on_calendar(event, person_id)
            and (after is None or calendars.moment(event.end_time) > after)
            and (before is None or calendars.moment(event.start_time) < before)
            and (needle is None or _matches_text(calendars, event, needle))
        ]
        key = (
            (lambda event: (event.start_time, event.calendar_event_id))
            if orderBy == "startTime"
            else (lambda event: (event.updated, event.calendar_event_id))
        )
        matched.sort(key=key)
        size = min(max(pageSize, 1), _MAX_EVENTS)
        offset = max(int(pageToken), 0) if pageToken else 0
        exhausted = offset + size >= len(matched)
        return {
            "events": [
                _event_json(calendars, event)
                for event in matched[offset : offset + size]
            ],
            "nextPageToken": None if exhausted else str(offset + size),
        }

    @server.tool()
    def get_event(eventId: str, calendarId: str | None = None) -> dict:
        """Read one event by id, optionally requiring it to sit on a
        particular person's calendar."""
        with connect_readonly(db_path) as connection:
            calendars = _load(connection)
        person_id = calendars.resolve(calendarId)
        for event in calendars.events:
            if event.calendar_event_id == eventId and calendars.on_calendar(
                event, person_id
            ):
                return _event_json(calendars, event)
        raise UnknownRefError(f"no event {eventId}")

    @server.tool()
    def list_calendars(pageSize: int = 100, pageToken: str | None = None) -> dict:
        """List the calendars this account can read: one per person who
        appears on an event, keyed by their email address."""
        with connect_readonly(db_path) as connection:
            calendars = _load(connection)
        owners = sorted(
            {event.organizer for event in calendars.events}
            | {
                attendee.person_id
                for attendees in calendars.attendees.values()
                for attendee in attendees
            }
        )
        mine = seat()
        items = [
            {
                "id": calendars.people[person_id].email_address,
                "summary": calendars.people[person_id].name,
                "primary": person_id == mine,
                "accessRole": "owner" if person_id == mine else "reader",
            }
            for person_id in owners
        ]
        size = min(max(pageSize, 1), _MAX_CALENDARS)
        offset = max(int(pageToken), 0) if pageToken else 0
        exhausted = offset + size >= len(items)
        return {
            "calendars": items[offset : offset + size],
            "nextPageToken": None if exhausted else str(offset + size),
        }
