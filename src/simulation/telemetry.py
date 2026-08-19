"""Per-day run telemetry: one JSON line per simulated day.

A multi-hour recording must be legible from another terminal. The writer
appends one canonical-JSON row per day (plus segment markers on
interrupt/resume) to ``telemetry.jsonl`` beside ``run.db``; ``tail -f``
is the live view and the run manager's ``status``/``report`` commands
read it back.
"""

import json
from collections.abc import Iterator
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DayRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = "day"
    day: str
    day_index: int = Field(ge=0)
    steps: int = Field(ge=0)
    events: dict[str, int] = Field(default_factory=dict)
    lm_calls: int = Field(ge=0, default=0)
    lm_network_calls: int = Field(ge=0, default=0)
    prompt_tokens: int = Field(ge=0, default=0)
    completion_tokens: int = Field(ge=0, default=0)
    rejections: int = Field(ge=0, default=0)
    batches: int = Field(ge=0, default=0)
    max_batch: int = Field(ge=0, default=0)
    wall_seconds: float = Field(ge=0.0, default=0.0)


class SegmentRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str = "segment"
    label: str
    day: str | None = None
    steps: int = Field(ge=0, default=0)
    reason: str = ""


class TelemetryWriter:
    def __init__(self, path: Path) -> None:
        self._path = path

    @property
    def path(self) -> Path:
        return self._path

    def append(self, row: DayRow | SegmentRow) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._path.open("a", encoding="utf-8") as handle:
            handle.write(row.model_dump_json() + "\n")


def read_rows(path: Path) -> Iterator[DayRow | SegmentRow]:
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            if json.loads(line).get("kind") == "segment":
                yield SegmentRow.model_validate_json(line)
            else:
                yield DayRow.model_validate_json(line)
