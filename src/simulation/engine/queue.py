"""Queue of scheduled drafts, totally ordered by (time, order).

Only the engine mints seq — at pop time, when a draft becomes a world event.
That keeps the world log gapless in seq and non-decreasing in time even when
resolutions schedule far-future events.
"""

import heapq

from pydantic import BaseModel, ConfigDict, Field

from core.events import EventDraft


class ScheduledEvent(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    time: int = Field(ge=0)
    order: int = Field(ge=0)
    draft: EventDraft


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[tuple[int, int], ScheduledEvent]] = []

    def push(self, item: ScheduledEvent) -> None:
        heapq.heappush(self._heap, ((item.time, item.order), item))

    def pop(self) -> ScheduledEvent:
        if not self._heap:
            raise IndexError("pop from empty EventQueue")
        return heapq.heappop(self._heap)[1]

    def peek(self) -> ScheduledEvent:
        if not self._heap:
            raise IndexError("peek at empty EventQueue")
        return self._heap[0][1]

    def __len__(self) -> int:
        return len(self._heap)

    def snapshot(self) -> tuple[ScheduledEvent, ...]:
        return tuple(item for _, item in sorted(self._heap, key=lambda p: p[0]))
