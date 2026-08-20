"""Project calendar events into the calendar database.

Event state folds in memory (validated on every fold, so a bad change is
a projection failure rather than a bad row), then every event and every
attendee lands once. Scheduling creates the row; updates and responses
move it, and ``updated`` tracks the last of either.
"""

import sqlite3
from collections.abc import Sequence

from core.events import Event
from core.events.calendar import (
    CalendarEventScheduledPayload,
    CalendarEventUpdatedPayload,
    CalendarResponsePayload,
)
from core.simtime import misread_unit
from tools.calendar.tables import (
    ATTENDEES,
    CALENDAR_EVENTS,
    Attendee,
    CalendarEvent,
)

# The event fields a calendar keeps, by the world log's name for them.
# A change to anything else names nothing this database serves.
FOLDED_FIELDS = {
    "title": "summary",
    "description": "description",
    "start": "start_time",
    "end": "end_time",
    "status": "status",
}

RESPONSE_STATUS = {
    "accept": "accepted",
    "decline": "declined",
    "tentative": "tentative",
}


def project(events: Sequence[Event], connection: sqlite3.Connection) -> None:
    scheduled: dict[str, CalendarEvent] = {}
    attendees: dict[str, dict[str, Attendee]] = {}
    # Starts written in the wrong unit are dropped rather than served.
    #
    # One recorded world put two wrong units through this one field: a
    # wall-clock time of day that had lost its date, and absolute Unix
    # timestamps landing in 2081. Neither raises -- each is a plausible
    # integer projecting into a plausible row -- and the served diary then
    # holds meetings before the firm opened.
    #
    # The test is causal rather than by magnitude, because with a midnight
    # epoch a first-day 08:45 meeting and a lost wall-clock time are the
    # same number. `core.simtime.misread_unit` compares the start against
    # the moment the scheduling was recorded; judging by size alone dropped
    # eight legitimate first-day meetings here.
    #
    # This removes provably corrupt rows; it never invents a replacement.
    # Which day a wall-clock time meant is not recoverable, so repairing one
    # would put a guess where an agent reads a fact. Responses and attendee
    # rows for a dropped event go with it, because a reference to an event
    # the calendar does not serve is worse than the absence of both.
    #
    # The writer is the real fix -- the referee grounding these accepts any
    # integer that is merely larger than the one before it. This is what a
    # downstream layer can do while a recording is in flight.
    quarantined: set[str] = set()
    for event in events:
        payload = event.payload
        if isinstance(payload, CalendarEventScheduledPayload) and misread_unit(
            int(payload.start), int(event.time)
        ):
            quarantined.add(payload.calendar_event_id)

    for event in events:
        payload = event.payload
        if getattr(payload, "calendar_event_id", None) in quarantined:
            continue
        if isinstance(payload, CalendarEventScheduledPayload):
            scheduled[payload.calendar_event_id] = CalendarEvent(
                calendar_event_id=payload.calendar_event_id,
                organizer=payload.organizer,
                summary=payload.title,
                description=payload.description,
                start_time=int(payload.start),
                end_time=int(payload.end),
                status="confirmed",
                created=int(event.time),
                updated=int(event.time),
            )
            attendees[payload.calendar_event_id] = {
                person: Attendee(
                    calendar_event_id=payload.calendar_event_id,
                    person_id=person,
                    response_status="needsAction",
                )
                for person in payload.attendees
            }
        elif isinstance(payload, CalendarEventUpdatedPayload):
            folded = scheduled[payload.calendar_event_id]
            update: dict[str, object] = {"updated": int(event.time)}
            for change in payload.changes:
                column = FOLDED_FIELDS.get(change.field)
                if column is not None and change.new is not None:
                    update[column] = change.new
            scheduled[payload.calendar_event_id] = CalendarEvent.model_validate(
                {**folded.model_dump(), **update}
            )
        elif isinstance(payload, CalendarResponsePayload):
            invited = attendees[payload.calendar_event_id]
            invited[payload.responder] = Attendee(
                calendar_event_id=payload.calendar_event_id,
                person_id=payload.responder,
                response_status=RESPONSE_STATUS[payload.response],
            )
            folded = scheduled[payload.calendar_event_id]
            scheduled[payload.calendar_event_id] = CalendarEvent.model_validate(
                {**folded.model_dump(), "updated": int(event.time)}
            )
    CALENDAR_EVENTS.insert(connection, scheduled.values())
    ATTENDEES.insert(
        connection,
        (
            invited[person]
            for invited in attendees.values()
            for person in sorted(invited)
        ),
    )
