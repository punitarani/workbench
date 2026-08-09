"""Per-entity attention: tag-prefix masks with deferred delivery.

"Heads-down until 15:00 unless it's a direct message" is the core mechanic
of a believable professional day.
"""

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events import Event
from workbench.core.simtime import SimTime


def matches_prefix(pattern: str, tag: str) -> bool:
    if not pattern:
        return False
    pattern_parts = pattern.split(".")
    tag_parts = tag.split(".")
    if len(pattern_parts) > len(tag_parts):
        return False
    return tag_parts[: len(pattern_parts)] == pattern_parts


class EntityAttention(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    heads_down_until: int | None = None
    allow: tuple[str, ...] = ()
    deferred: tuple[Event, ...] = ()


class AttentionBookState(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: tuple[tuple[str, EntityAttention], ...] = Field(default=())


class AttentionBook:
    def __init__(self, entities: tuple[str, ...]) -> None:
        self._entries: dict[str, EntityAttention] = {
            entity: EntityAttention() for entity in entities
        }

    def _entry(self, entity: str) -> EntityAttention:
        return self._entries[entity]

    def should_deliver(self, entity: str, event: Event, *, now: SimTime) -> bool:
        entry = self._entry(entity)
        if entry.heads_down_until is None or int(now) >= entry.heads_down_until:
            return True
        return any(matches_prefix(pattern, event.tag) for pattern in entry.allow)

    def set_heads_down(
        self, entity: str, *, until: SimTime, allow: tuple[str, ...]
    ) -> None:
        entry = self._entry(entity)
        self._entries[entity] = entry.model_copy(
            update={"heads_down_until": int(until), "allow": allow}
        )

    def clear(self, entity: str) -> None:
        entry = self._entry(entity)
        self._entries[entity] = entry.model_copy(
            update={"heads_down_until": None, "allow": ()}
        )

    def defer(self, entity: str, event: Event) -> None:
        entry = self._entry(entity)
        self._entries[entity] = entry.model_copy(
            update={"deferred": (*entry.deferred, event)}
        )

    def flush(self, entity: str) -> tuple[Event, ...]:
        entry = self._entry(entity)
        deferred = entry.deferred
        self._entries[entity] = entry.model_copy(update={"deferred": ()})
        return deferred

    def get_state(self) -> AttentionBookState:
        return AttentionBookState(
            entries=tuple(sorted(self._entries.items(), key=lambda pair: pair[0]))
        )

    def set_state(self, state: AttentionBookState) -> None:
        for entity, entry in state.entries:
            if entity in self._entries:
                self._entries[entity] = entry
