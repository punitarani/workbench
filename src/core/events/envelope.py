from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from core.events.payloads import EventPayload
from core.ids import EntityName, EventId
from core.simtime import SimDuration, SimTime


def event_id_for(seq: int) -> EventId:
    return EventId(f"evt-{seq:06d}")


class Event(BaseModel):
    """The envelope: routing, ordering, and causality are typed; prose lives inside."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seq: int = Field(ge=0)
    event_id: EventId | None = None
    time: SimTime = Field(ge=0)
    tag: str
    source: EntityName
    caused_by: EventId | None = None
    payload: EventPayload

    @model_validator(mode="after")
    def _derive_and_check(self) -> Event:
        expected = event_id_for(self.seq)
        if self.event_id is None:
            object.__setattr__(self, "event_id", expected)
        elif self.event_id != expected:
            raise ValueError(f"event_id {self.event_id} does not match seq {self.seq}")
        if self.tag != self.payload.kind:
            raise ValueError(f"tag {self.tag!r} != payload.kind {self.payload.kind!r}")
        return self

    def sort_key(self) -> tuple[int, int]:
        return (int(self.time), self.seq)


class EventDraft(BaseModel):
    """What resolution produces. Only the engine mints seq and absolute time."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    tag: str
    source: EntityName
    caused_by: EventId | None = None
    payload: EventPayload
    delay: SimDuration = SimDuration(0)

    @model_validator(mode="after")
    def _tag_matches(self) -> EventDraft:
        if self.tag != self.payload.kind:
            raise ValueError(f"tag {self.tag!r} != payload.kind {self.payload.kind!r}")
        return self

    def to_event(self, *, seq: int, time: SimTime) -> Event:
        data: dict[str, Any] = {
            "seq": seq,
            "time": time,
            "tag": self.tag,
            "source": self.source,
            "caused_by": self.caused_by,
            "payload": self.payload,
        }
        return Event(**data)
