from typing import Literal

from pydantic import Field, model_validator

from workbench.core.events._base import Payload
from workbench.core.ids import CalendarEventId, MeetingId, PersonId
from workbench.core.simtime import SimTime


class TranscriptTurn(Payload):
    speaker: PersonId
    text: str


class SimMeetingConvenePayload(Payload):
    """A calendar event's start time arrived: open the meeting and give
    the first speaker a turn. Attendees are entity names so footprints
    and routing need no lookup."""

    kind: Literal["sim.meeting.convene"]
    meeting_id: MeetingId
    calendar_event_id: CalendarEventId | None
    title: str
    description: str = ""
    attendees: tuple[str, ...] = Field(min_length=2)
    duration_seconds: int = Field(ge=60, default=1800)


class SimMeetingTurnPayload(Payload):
    """One utterance slot in an open meeting."""

    kind: Literal["sim.meeting.turn"]
    meeting_id: MeetingId
    speaker: str
    turn_index: int = Field(ge=0)
    attendees: tuple[str, ...] = Field(min_length=2)


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
