from typing import Literal

from pydantic import Field, model_validator

from workbench.core.events._base import Payload
from workbench.core.events.tickets import FieldChange
from workbench.core.ids import CalendarEventId, PersonId
from workbench.core.simtime import SimTime


class CalendarEventScheduledPayload(Payload):
    kind: Literal["calendar.event.scheduled"]
    calendar_event_id: CalendarEventId
    organizer: PersonId
    title: str
    start: SimTime
    end: SimTime
    attendees: tuple[PersonId, ...] = Field(min_length=1)
    description: str

    @model_validator(mode="after")
    def _end_after_start(self) -> CalendarEventScheduledPayload:
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class CalendarEventUpdatedPayload(Payload):
    kind: Literal["calendar.event.updated"]
    calendar_event_id: CalendarEventId
    actor: PersonId
    changes: tuple[FieldChange, ...] = Field(min_length=1)


class CalendarResponsePayload(Payload):
    kind: Literal["calendar.response"]
    calendar_event_id: CalendarEventId
    responder: PersonId
    response: Literal["accept", "decline", "tentative"]
