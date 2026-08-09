"""Event queue totally ordered by (time, seq)."""

import heapq

from workbench.core.events import Event


class EventQueue:
    def __init__(self) -> None:
        self._heap: list[tuple[tuple[int, int], Event]] = []

    def push(self, event: Event) -> None:
        heapq.heappush(self._heap, (event.sort_key(), event))

    def pop(self) -> Event:
        if not self._heap:
            raise IndexError("pop from empty EventQueue")
        return heapq.heappop(self._heap)[1]

    def peek(self) -> Event:
        if not self._heap:
            raise IndexError("peek at empty EventQueue")
        return self._heap[0][1]

    def __len__(self) -> int:
        return len(self._heap)

    def snapshot(self) -> tuple[Event, ...]:
        return tuple(event for _, event in sorted(self._heap, key=lambda p: p[0]))
