"""Content-addressed transcript store: repeated identical prompts stored once."""

from pydantic import BaseModel, ConfigDict

from workbench.core.hashing import content_hash
from workbench.simulation.entity.context import ContextBlock


class TranscriptEntry(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    entity: str
    phase: str
    blocks: tuple[ContextBlock, ...]
    note: str = ""


class TranscriptStore:
    def __init__(self) -> None:
        self._entries: dict[str, TranscriptEntry] = {}

    def add(self, entry: TranscriptEntry) -> str:
        key = content_hash(entry)
        self._entries.setdefault(key, entry)
        return key

    def entries(self) -> tuple[TranscriptEntry, ...]:
        return tuple(self._entries[key] for key in sorted(self._entries))
