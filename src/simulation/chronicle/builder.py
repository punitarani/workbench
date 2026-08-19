"""Append day segments to one world log.

The chronicle owns the envelope: callers hand it payload drafts carrying
intra-day clocks, and it assigns absolute time, sequence continuation, and
the ``sim.day.started`` / ``sim.day.ended`` boundary markers. Each day is
appended with ``WorldLogWriter.append_to``, so a partially built log is
always a valid prefix; a day whose drafts regress is rejected before any
byte is written.
"""

from collections.abc import Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from core.errors import WorldLogIntegrityError
from core.events import Event, EventPayload
from core.events.control import SimDayEndedPayload, SimDayStartedPayload
from core.ids import EntityName, EventId
from core.simtime import SimDuration, SimTime
from core.worldlog import WorldLogWriter, read_events, validate_events
from simulation.chronicle.calendar import SECONDS_PER_DAY, CalendarWindow
from simulation.errors import ChronicleError


class TimedDraft(BaseModel):
    """A payload at an intra-day clock; the chronicle mints the envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at: SimDuration = Field(ge=0, lt=SECONDS_PER_DAY)
    source: EntityName
    payload: EventPayload
    caused_by: EventId | None = None


class Chronicle:
    """Builds one multi-day world log: genesis first, then ascending days."""

    def __init__(self, path: Path, *, window: CalendarWindow) -> None:
        self._path = path
        self._window = window
        self._next_seq = 0
        self._last_time = 0
        self._last_day_index = -1

    def write_genesis(self, events: Sequence[Event]) -> None:
        if self._next_seq != 0:
            raise ChronicleError("genesis is already written")
        if not events:
            raise ChronicleError("genesis must contain at least sim.run.started")
        with WorldLogWriter(self._path) as writer:
            for event in events:
                writer.append(event)
        self._next_seq = len(events)
        self._last_time = int(events[-1].time)

    def add_procedural_day(self, day_index: int, drafts: Sequence[TimedDraft]) -> None:
        if self._next_seq == 0:
            raise ChronicleError("write genesis before adding days")
        if day_index <= self._last_day_index:
            raise ChronicleError(
                f"day {day_index} does not follow day {self._last_day_index}"
            )
        day = self._window.iso_date(day_index)
        offset = int(self._window.day_offset(day_index))
        clocks = [int(draft.at) for draft in drafts]
        for previous, current in zip(clocks, clocks[1:], strict=False):
            if current < previous:
                raise ChronicleError(
                    f"day {day}: draft at {current}s regresses from {previous}s"
                )

        writer = WorldLogWriter.append_to(
            self._path, next_seq=self._next_seq, last_time=self._last_time
        )
        try:
            started = SimDayStartedPayload(kind="sim.day.started", day=day)
            self._append(writer, "gm", started, time=offset)
            for draft in drafts:
                self._append(
                    writer,
                    draft.source,
                    draft.payload,
                    time=offset + int(draft.at),
                    caused_by=draft.caused_by,
                )
            ended = SimDayEndedPayload(kind="sim.day.ended", day=day)
            self._append(writer, "gm", ended, time=offset + SECONDS_PER_DAY - 1)
        finally:
            writer.close()
        self._last_day_index = day_index

    def _append(
        self,
        writer: WorldLogWriter,
        source: str,
        payload: EventPayload,
        *,
        time: int,
        caused_by: EventId | None = None,
    ) -> None:
        event = Event(
            seq=self._next_seq,
            time=SimTime(time),
            tag=payload.kind,
            source=EntityName(source),
            caused_by=caused_by,
            payload=payload,
        )
        writer.append(event)
        self._next_seq += 1
        self._last_time = time

    def finish(self) -> tuple[Event, ...]:
        events = read_events(self._path)
        report = validate_events(events)
        if report.findings:
            details = "; ".join(
                f"seq {finding.seq} {finding.code}: {finding.detail}"
                for finding in report.findings[:5]
            )
            raise WorldLogIntegrityError(
                f"chronicle at {self._path} is incoherent: {details}"
            )
        return tuple(events)
