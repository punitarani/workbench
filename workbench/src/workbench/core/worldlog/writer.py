"""Append-only JSONL writer enforcing the log's ordering invariants at write time.

Synchronous by design: appends happen from the engine's single resolution
point, and byte-stability matters more than throughput here.
"""

from pathlib import Path
from types import TracebackType
from typing import IO

from workbench.core.errors import WorldLogOrderingError
from workbench.core.events import Event

RUN_STARTED_TAG = "sim.run.started"


class WorldLogWriter:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._handle: IO[bytes] | None = None
        self._next_seq = 0
        self._last_time = 0

    def __enter__(self) -> WorldLogWriter:
        self._handle = self._path.open("xb")
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def append(self, event: Event) -> None:
        if self._handle is None:
            raise WorldLogOrderingError("writer is not open")
        if self._next_seq == 0 and event.tag != RUN_STARTED_TAG:
            raise WorldLogOrderingError(
                f"first event must be {RUN_STARTED_TAG}, got {event.tag}"
            )
        if event.seq != self._next_seq:
            raise WorldLogOrderingError(
                f"expected seq {self._next_seq}, got {event.seq}"
            )
        if int(event.time) < self._last_time:
            raise WorldLogOrderingError(
                f"time regressed from {self._last_time} to {int(event.time)}"
            )
        self._handle.write(event.model_dump_json().encode("utf-8"))
        self._handle.write(b"\n")
        self._next_seq += 1
        self._last_time = int(event.time)

    def close(self) -> None:
        if self._handle is not None:
            self._handle.flush()
            self._handle.close()
            self._handle = None
