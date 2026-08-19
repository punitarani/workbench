"""Row models and tables for the calendar database.

Times are simulated seconds, like every other projection; the served
ISO-8601 moments derive from the shared meta table's epoch. The columns
are ``start_time``/``end_time`` rather than ``start``/``end`` because END
is a SQLite keyword.
"""

from typing import Annotated, Literal

from pydantic import BaseModel

from tools.db import Id, Ref, Table


class CalendarEvent(BaseModel):
    calendar_event_id: Annotated[str, Id("calendar.event")]
    organizer: Annotated[str, Ref("person")]
    summary: str
    description: str
    start_time: int
    end_time: int
    # Google's own status vocabulary is confirmed/tentative/cancelled, and a
    # freshly scheduled event is "confirmed". A workplace may fold a richer
    # status onto an event ("vacated - continued per clerk notice"); that
    # text is kept and served verbatim rather than bucketed into one of the
    # three, which would drop what actually happened.
    status: str
    created: int
    updated: int


class Attendee(BaseModel):
    calendar_event_id: Annotated[str, Ref("calendar.event")]
    person_id: Annotated[str, Ref("person")]
    response_status: Literal["needsAction", "accepted", "declined", "tentative"]


class EventRecurrence(BaseModel):
    """RFC 5545 rules for a recurring series (RRULE/RDATE/EXDATE lines)."""

    calendar_event_id: Annotated[str, Ref("calendar.event")]
    rule: str


CALENDAR_EVENTS = Table(
    "calendar_events", CalendarEvent, primary_key=("calendar_event_id",)
)
RECURRENCE = Table("event_recurrence", EventRecurrence)
ATTENDEES = Table("attendees", Attendee, primary_key=("calendar_event_id", "person_id"))
