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
    RECURRENCE,
    Attendee,
    CalendarEvent,
    EventRecurrence,
)
from workbench.tools.db import connect_readonly, connect_readwrite
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
# Google's own vocabularies, verbatim.
type OrderBy = Literal["default", "startTime", "startTimeDesc", "lastModified"]
type NotificationLevel = Literal[
    "NOTIFICATION_LEVEL_UNSPECIFIED", "NONE", "EXTERNAL_ONLY", "ALL"
]
type ResponseStatus = Literal["accepted", "declined", "tentative"]
type EventType = Literal[
    "EVENT_TYPE_UNSPECIFIED",
    "DEFAULT",
    "OUT_OF_OFFICE",
    "FOCUS_TIME",
    "WORKING_LOCATION",
    "BIRTHDAY",
    "FROM_GMAIL",
]
_DEFAULT_EVENT_TYPES = ("DEFAULT", "OUT_OF_OFFICE", "FOCUS_TIME", "FROM_GMAIL")


@dataclass(frozen=True, slots=True)
class _Calendars:
    events: list[CalendarEvent]
    attendees: dict[str, list[Attendee]]
    people: dict[str, Person]
    recurrence: dict[str, list[str]]
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

    def person_for_email(self, email: str) -> str | None:
        """The person behind an attendee address, or None if they are a
        stranger to this workspace."""

        needle = email.strip().lower()
        for person_id, person in self.people.items():
            if needle in (person_id.lower(), person.email_address.lower()):
                return person_id
        return None

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
    recurrence: dict[str, list[str]] = {}
    for row in RECURRENCE.select(connection):
        recurrence.setdefault(row.calendar_event_id, []).append(row.rule)
    return _Calendars(
        events=events,
        attendees={event.calendar_event_id: [] for event in events} | attendees,
        recurrence=recurrence,
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
        "recurrence": list(calendars.recurrence.get(event.calendar_event_id, ())),
        "eventType": _event_type(event),
        "availability": (
            "AVAILABILITY_FREE"
            if _event_type(event) in ("OUT_OF_OFFICE", "WORKING_LOCATION")
            else "AVAILABILITY_BUSY"
        ),
    }


def _event_type(event: CalendarEvent) -> str:
    """Google's eventType, inferred from how the workplace uses the event.

    The record has no eventType column — the world models meetings, out of
    office, and focus blocks as ordinary events — so the served value is
    derived from the summary rather than invented per call.
    """

    summary = event.summary.lower()
    if any(word in summary for word in ("out of office", "ooo", "pto", "vacation")):
        return "OUT_OF_OFFICE"
    if "focus" in summary or "heads-down" in summary:
        return "FOCUS_TIME"
    return "DEFAULT"


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


def _clock(value: object, fallback: int) -> int:
    """An "HH:mm" preference as an hour, tolerating a bare hour."""

    if value is None:
        return fallback
    text = str(value)
    head = text.split(":")[0]
    return int(head) if head.isdigit() else fallback


def _seconds(value: str, epoch: datetime) -> int:
    return int((_boundary(value, epoch) - epoch).total_seconds())


def _next_event_id(connection: sqlite3.Connection) -> str:
    existing = CALENDAR_EVENTS.select(connection)
    return f"cal-{len(existing) + 1:06d}"


def _find(calendars: _Calendars, event_id: str) -> CalendarEvent:
    for event in calendars.events:
        if event.calendar_event_id == event_id:
            return event
    raise UnknownRefError(f"no event {event_id}")


def _sole_seat(calendars: _Calendars) -> str:
    """The acting person when no seat is set.

    An unseated server reads org-wide, but a write has to be *somebody*.
    Rather than guess, the organizer of the most recent event stands in —
    deterministic, and in a seated rollout (the normal case) this never
    runs.
    """

    if not calendars.events:
        raise UnknownRefError("no calendar to write to")
    return max(
        calendars.events, key=lambda event: (event.start_time, event.calendar_event_id)
    ).organizer


def register(server: MCPServer, db_path: Path) -> None:
    @server.tool()
    def list_events(
        calendarId: str | None = None,
        startTime: str | None = None,
        endTime: str | None = None,
        fullText: str | None = None,
        orderBy: OrderBy = "startTime",
        pageSize: int = _MAX_EVENTS,
        pageToken: str | None = None,
        timeZone: str | None = None,
        eventType: list[str] | None = None,
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
        if eventType:
            wanted = {value.upper() for value in eventType}
            matched = [
                event for event in matched if _event_type(event).upper() in wanted
            ]
        if orderBy == "lastModified":
            matched.sort(key=lambda event: (event.updated, event.calendar_event_id))
        elif orderBy == "startTimeDesc":
            matched.sort(key=lambda event: (-event.start_time, event.calendar_event_id))
        else:
            matched.sort(key=lambda event: (event.start_time, event.calendar_event_id))
        size = min(max(pageSize, 1), _MAX_EVENTS)
        offset = max(int(pageToken), 0) if pageToken else 0
        exhausted = offset + size >= len(matched)
        return {
            "timeZone": timeZone or str(calendars.epoch.tzinfo),
            "accessRole": "owner" if person_id else "reader",
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

    @server.tool()
    def search_events(
        query: str, pageSize: int = _MAX_EVENTS, pageToken: str | None = None
    ) -> dict:
        """Search this seat's primary calendar by text."""
        with connect_readonly(db_path) as connection:
            calendars = _load(connection)
        person_id = calendars.resolve(_PRIMARY)
        needle = query.lower()
        matched = [
            event
            for event in calendars.events
            if calendars.on_calendar(event, person_id)
            and _matches_text(calendars, event, needle)
        ]
        matched.sort(key=lambda event: (event.start_time, event.calendar_event_id))
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
    def suggest_time(
        attendeeEmails: list[str],
        startTime: str,
        endTime: str,
        timeZone: str | None = None,
        durationMinutes: int = 30,
        preferences: dict | None = None,
    ) -> dict:
        """Free slots of ``durationMinutes`` inside the window where every
        named attendee is free."""
        del timeZone
        options = preferences or {}
        with connect_readonly(db_path) as connection:
            calendars = _load(connection)
        window_start = _boundary(startTime, calendars.epoch)
        window_end = _boundary(endTime, calendars.epoch)
        people = [calendars.person_for_email(email) for email in attendeeEmails]
        busy: list[tuple[datetime, datetime]] = []
        for event in calendars.events:
            attending = {
                a.person_id for a in calendars.attendees[event.calendar_event_id]
            } | {event.organizer}
            if attending & {p for p in people if p}:
                busy.append(
                    (
                        calendars.moment(event.start_time),
                        calendars.moment(event.end_time),
                    )
                )
        busy.sort()
        step = timedelta(minutes=30)
        span = timedelta(minutes=max(1, durationMinutes))
        start_hour = _clock(options.get("startHour"), 9)
        end_hour = _clock(options.get("endHour"), 17)
        exclude_weekends = bool(options.get("excludeWeekends", True))
        limit = int(options.get("pageSize", 5))
        slots = []
        cursor = window_start
        while cursor + span <= window_end and len(slots) < limit:
            finish = cursor + span
            in_hours = start_hour <= cursor.hour < end_hour and finish.hour <= end_hour
            weekday_ok = not exclude_weekends or cursor.weekday() < 5
            clear = all(finish <= s or cursor >= e for s, e in busy)
            if in_hours and weekday_ok and clear:
                slots.append(
                    {
                        "start": {"dateTime": cursor.isoformat()},
                        "end": {"dateTime": finish.isoformat()},
                    }
                )
                cursor = finish
            else:
                cursor += step
        return {"timeSlots": slots}

    @server.tool()
    def create_event(
        summary: str,
        startTime: str,
        endTime: str,
        calendarId: str | None = None,
        description: str = "",
        location: str = "",
        allDay: bool = False,
        timeZone: str | None = None,
        attendees: list[dict] | None = None,
        recurrenceData: list[str] | None = None,
        notificationLevel: NotificationLevel = "ALL",
        visibility: str = "default",
        eventType: EventType = "DEFAULT",
    ) -> dict:
        """Schedule an event. Times are ISO-8601 in the workspace timezone."""
        del allDay, timeZone, notificationLevel, visibility, eventType
        with connect_readwrite(db_path) as connection:
            calendars = _load(connection)
            organizer = calendars.resolve(calendarId) or _sole_seat(calendars)
            start = _seconds(startTime, calendars.epoch)
            end = _seconds(endTime, calendars.epoch)
            if end <= start:
                raise UnknownRefError("endTime must be after startTime")
            event_id = _next_event_id(connection)
            now = max((event.updated for event in calendars.events), default=0)
            CALENDAR_EVENTS.insert(
                connection,
                [
                    CalendarEvent(
                        calendar_event_id=event_id,
                        organizer=organizer,
                        summary=summary,
                        description=description or location,
                        start_time=start,
                        end_time=end,
                        status="confirmed",
                        created=now,
                        updated=now,
                    )
                ],
            )
            rows = [
                Attendee(
                    calendar_event_id=event_id,
                    person_id=organizer,
                    response_status="accepted",
                )
            ]
            for attendee in attendees or []:
                person = calendars.person_for_email(str(attendee.get("email", "")))
                if person is None or person == organizer:
                    continue
                rows.append(
                    Attendee(
                        calendar_event_id=event_id,
                        person_id=person,
                        response_status="needsAction",
                    )
                )
            ATTENDEES.insert(connection, rows)
            if recurrenceData:
                RECURRENCE.insert(
                    connection,
                    [
                        EventRecurrence(calendar_event_id=event_id, rule=rule)
                        for rule in recurrenceData
                    ],
                )
            connection.commit()
            calendars = _load(connection)
        return _event_json(calendars, _find(calendars, event_id))

    @server.tool()
    def update_event(
        eventId: str,
        calendarId: str | None = None,
        summary: str | None = None,
        description: str | None = None,
        location: str | None = None,
        startTime: str | None = None,
        endTime: str | None = None,
        timeZone: str | None = None,
        notificationLevel: NotificationLevel = "ALL",
        addedAttendees: list[dict] | None = None,
        removedAttendeeEmails: list[str] | None = None,
    ) -> dict:
        """Change an event. Unset fields are left alone; attendees are
        added and removed as deltas, the way the official tool does it."""
        del calendarId, timeZone, notificationLevel
        with connect_readwrite(db_path) as connection:
            calendars = _load(connection)
            event = _find(calendars, eventId)
            start = (
                event.start_time
                if startTime is None
                else _seconds(startTime, calendars.epoch)
            )
            duration = event.end_time - event.start_time
            end = (
                start + duration
                if endTime is None
                else _seconds(endTime, calendars.epoch)
            )
            if end <= start:
                raise UnknownRefError("endTime must be after startTime")
            connection.execute(
                "UPDATE calendar_events SET summary=?, description=?, "
                "start_time=?, end_time=?, updated=? WHERE calendar_event_id=?",
                (
                    event.summary if summary is None else summary,
                    event.description
                    if description is None and location is None
                    else (description or location or event.description),
                    start,
                    end,
                    max(event.updated, end),
                    eventId,
                ),
            )
            for email in removedAttendeeEmails or []:
                person = calendars.person_for_email(email)
                if person:
                    connection.execute(
                        "DELETE FROM attendees WHERE calendar_event_id=? "
                        "AND person_id=?",
                        (eventId, person),
                    )
            existing = {a.person_id for a in calendars.attendees[eventId]}
            fresh = []
            for attendee in addedAttendees or []:
                person = calendars.person_for_email(str(attendee.get("email", "")))
                if person and person not in existing:
                    fresh.append(
                        Attendee(
                            calendar_event_id=eventId,
                            person_id=person,
                            response_status="needsAction",
                        )
                    )
            if fresh:
                ATTENDEES.insert(connection, fresh)
            connection.commit()
            calendars = _load(connection)
        return _event_json(calendars, _find(calendars, eventId))

    @server.tool()
    def delete_event(
        eventId: str,
        calendarId: str | None = None,
        notificationLevel: NotificationLevel = "ALL",
    ) -> dict:
        """Cancel an event. Returns the cancelled event, as the official
        tool does — a cancellation is part of the record, not an erasure."""
        del calendarId, notificationLevel
        with connect_readwrite(db_path) as connection:
            calendars = _load(connection)
            _find(calendars, eventId)
            connection.execute(
                "UPDATE calendar_events SET status='cancelled' "
                "WHERE calendar_event_id=?",
                (eventId,),
            )
            connection.commit()
            calendars = _load(connection)
        return _event_json(calendars, _find(calendars, eventId))

    @server.tool()
    def respond_to_event(
        eventId: str,
        responseStatus: ResponseStatus,
        calendarId: str | None = None,
        notificationLevel: NotificationLevel = "ALL",
        responseComment: str = "",
    ) -> dict:
        """RSVP to an invitation as this seat."""
        del notificationLevel, responseComment
        with connect_readwrite(db_path) as connection:
            calendars = _load(connection)
            _find(calendars, eventId)
            person_id = calendars.resolve(calendarId) or _sole_seat(calendars)
            updated = connection.execute(
                "UPDATE attendees SET response_status=? WHERE calendar_event_id=? "
                "AND person_id=?",
                (responseStatus, eventId, person_id),
            ).rowcount
            if not updated:
                ATTENDEES.insert(
                    connection,
                    [
                        Attendee(
                            calendar_event_id=eventId,
                            person_id=person_id,
                            response_status=responseStatus,
                        )
                    ],
                )
            connection.commit()
            calendars = _load(connection)
        return _event_json(calendars, _find(calendars, eventId))
