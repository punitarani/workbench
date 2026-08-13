"""Typed identifiers and deterministic id minting."""

from typing import Annotated, NewType

from pydantic import BaseModel, Field, StringConstraints, TypeAdapter, field_serializer

EntityName = NewType("EntityName", str)
ComponentName = NewType("ComponentName", str)
PrefabName = NewType("PrefabName", str)

EventId = NewType("EventId", str)
PersonId = NewType("PersonId", str)
ThreadId = NewType("ThreadId", str)
MessageId = NewType("MessageId", str)
ConversationId = NewType("ConversationId", str)
ChatMessageId = NewType("ChatMessageId", str)
DocumentId = NewType("DocumentId", str)
TicketId = NewType("TicketId", str)
OrgId = NewType("OrgId", str)
CalendarEventId = NewType("CalendarEventId", str)
MeetingId = NewType("MeetingId", str)

Slug = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z0-9-]*$")]
_SLUG = TypeAdapter[str](Slug)


class IdMinter(BaseModel):
    """Mints ids like ``msg-000001``. Snapshot-serialized, so key order is canonical."""

    counters: dict[str, int] = Field(default_factory=dict)

    def mint(self, prefix: str) -> str:
        _SLUG.validate_python(prefix)
        count = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = count
        return f"{prefix}-{count:06d}"

    @field_serializer("counters")
    def _sorted_counters(self, counters: dict[str, int]) -> dict[str, int]:
        return dict(sorted(counters.items()))
