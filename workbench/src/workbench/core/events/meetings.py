from typing import Literal

from pydantic import Field, model_validator

from workbench.core.events._base import Payload
from workbench.core.ids import CalendarEventId, MeetingId, PersonId
from workbench.core.simtime import SimTime


class TranscriptTurn(Payload):
    speaker: PersonId
    text: str


class MeetingTranscriptPayload(Payload):
    kind: Literal["meeting.transcript"]
    meeting_id: MeetingId
    calendar_event_id: CalendarEventId | None
    attendees: tuple[PersonId, ...] = Field(min_length=1)
    started: SimTime
    ended: SimTime
    turns: tuple[TranscriptTurn, ...]

    @model_validator(mode="after")
    def _ends_after_start(self) -> MeetingTranscriptPayload:
        if self.ended <= self.started:
            raise ValueError("ended must be after started")
        return self
