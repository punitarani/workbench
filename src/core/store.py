"""The per-run SQLite store: events, scheduled queue, snapshots, run metadata.

One ``run.db`` per run, WAL mode, ``autocommit=False`` — nothing reaches disk
outside an explicit commit, so an engine step can be made all-or-nothing.
``seq`` is the events table's primary key and appends enforce contiguity, so
the world log's gapless invariant is structural here, not conventional.

The JSONL world log remains the canonical export format; ``export_jsonl``
produces bytes identical to ``WorldLogWriter`` output for the same events.
"""

import json
import sqlite3
from collections.abc import Iterator
from pathlib import Path
from types import TracebackType

from pydantic import BaseModel, ConfigDict

from core.errors import WorkbenchError
from core.events import Event, EventDraft

_SCHEMA = """
CREATE TABLE events (
    seq INTEGER PRIMARY KEY,
    time INTEGER NOT NULL,
    tag TEXT NOT NULL,
    source TEXT NOT NULL,
    caused_by TEXT,
    payload TEXT NOT NULL
);
CREATE INDEX events_time ON events (time, seq);
CREATE TABLE scheduled (
    time INTEGER NOT NULL,
    ord INTEGER PRIMARY KEY,
    draft TEXT NOT NULL
);
CREATE INDEX scheduled_time ON scheduled (time, ord);
CREATE TABLE snapshots (
    step INTEGER PRIMARY KEY,
    taken_seq INTEGER NOT NULL,
    state TEXT NOT NULL
);
CREATE TABLE run_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


class RunStoreError(WorkbenchError):
    """The store refused an operation that would corrupt run state."""


class StoredSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    step: int
    taken_seq: int
    state: str


class SqliteRunStore:
    def __init__(self, connection: sqlite3.Connection, path: Path) -> None:
        self._connection = connection
        self._path = path
        row = connection.execute(
            "SELECT COALESCE(MAX(seq) + 1, 0),"
            " COALESCE((SELECT time FROM events ORDER BY seq DESC LIMIT 1), 0)"
            " FROM events"
        ).fetchone()
        self._next_seq, self._last_time = int(row[0]), int(row[1])

    @classmethod
    def create(cls, path: Path) -> SqliteRunStore:
        if path.exists():
            raise RunStoreError(f"run store already exists: {path}")
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, autocommit=True)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.executescript(_SCHEMA)
        connection.autocommit = False
        return cls(connection, path)

    @classmethod
    def open(cls, path: Path) -> SqliteRunStore:
        if not path.exists():
            raise RunStoreError(f"run store not found: {path}")
        connection = sqlite3.connect(path, autocommit=True)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.autocommit = False
        return cls(connection, path)

    @property
    def path(self) -> Path:
        return self._path

    def head(self) -> tuple[int, int]:
        """(next_seq, last committed-or-pending event time)."""
        return (self._next_seq, self._last_time)

    def append_event(self, event: Event) -> None:
        if event.seq != self._next_seq:
            raise RunStoreError(f"expected seq {self._next_seq}, got {event.seq}")
        if self._next_seq == 0 and event.tag != "sim.run.started":
            raise RunStoreError(f"first event must be sim.run.started, got {event.tag}")
        if int(event.time) < self._last_time:
            raise RunStoreError(
                f"time regressed from {self._last_time} to {int(event.time)}"
            )
        self._connection.execute(
            "INSERT INTO events (seq, time, tag, source, caused_by, payload)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                event.seq,
                int(event.time),
                event.tag,
                event.source,
                event.caused_by,
                event.payload.model_dump_json(),
            ),
        )
        self._next_seq += 1
        self._last_time = int(event.time)

    def read_events(self, since_seq: int = 0) -> Iterator[Event]:
        cursor = self._connection.execute(
            "SELECT seq, time, tag, source, caused_by, payload FROM events"
            " WHERE seq >= ? ORDER BY seq",
            (since_seq,),
        )
        for seq, time, tag, source, caused_by, payload in cursor:
            yield Event.model_validate(
                {
                    "seq": seq,
                    "time": time,
                    "tag": tag,
                    "source": source,
                    "caused_by": caused_by,
                    "payload": json.loads(payload),
                }
            )

    def queue_add(self, *, time: int, order: int, draft: EventDraft) -> None:
        self._connection.execute(
            "INSERT INTO scheduled (time, ord, draft) VALUES (?, ?, ?)",
            (time, order, draft.model_dump_json()),
        )

    def queue_remove(self, *, order: int) -> None:
        removed = self._connection.execute(
            "DELETE FROM scheduled WHERE ord = ?", (order,)
        ).rowcount
        if removed != 1:
            raise RunStoreError(f"no scheduled row with order {order}")

    def queue_rows(self) -> list[tuple[int, int, EventDraft]]:
        return [
            (time, order, EventDraft.model_validate_json(draft))
            for time, order, draft in self._connection.execute(
                "SELECT time, ord, draft FROM scheduled ORDER BY time, ord"
            )
        ]

    def put_snapshot(self, *, step: int, taken_seq: int, state: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO snapshots (step, taken_seq, state)"
            " VALUES (?, ?, ?)",
            (step, taken_seq, state),
        )

    def prune_snapshots(self, *, keep: int) -> None:
        """Drop all but the newest ``keep`` snapshots. Snapshots grow with
        cast size and memory span; a long run keeps a small rolling set."""

        if keep < 1:
            raise ValueError(f"keep must be positive, got {keep}")
        self._connection.execute(
            "DELETE FROM snapshots WHERE step NOT IN "
            "(SELECT step FROM snapshots ORDER BY step DESC LIMIT ?)",
            (keep,),
        )

    def latest_snapshot(self) -> StoredSnapshot | None:
        row = self._connection.execute(
            "SELECT step, taken_seq, state FROM snapshots ORDER BY step DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        return StoredSnapshot(step=row[0], taken_seq=row[1], state=row[2])

    def set_meta(self, key: str, value: str) -> None:
        self._connection.execute(
            "INSERT OR REPLACE INTO run_meta (key, value) VALUES (?, ?)",
            (key, value),
        )

    def get_meta(self, key: str) -> str | None:
        row = self._connection.execute(
            "SELECT value FROM run_meta WHERE key = ?", (key,)
        ).fetchone()
        return None if row is None else row[0]

    def commit(self) -> None:
        self._connection.commit()

    def transaction(self) -> _Transaction:
        return _Transaction(self)

    def rollback(self) -> None:
        self._connection.rollback()
        row = self._connection.execute(
            "SELECT COALESCE(MAX(seq) + 1, 0),"
            " COALESCE((SELECT time FROM events ORDER BY seq DESC LIMIT 1), 0)"
            " FROM events"
        ).fetchone()
        self._next_seq, self._last_time = int(row[0]), int(row[1])

    def close(self) -> None:
        self._connection.close()


class _Transaction:
    def __init__(self, store: SqliteRunStore) -> None:
        self._store = store

    def __enter__(self) -> SqliteRunStore:
        return self._store

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._store.commit()
        else:
            self._store.rollback()


def export_jsonl(store: SqliteRunStore, path: Path) -> None:
    """Write the canonical JSONL world log — byte-identical to WorldLogWriter."""
    with path.open("wb") as handle:
        for event in store.read_events():
            handle.write(event.model_dump_json().encode("utf-8"))
            handle.write(b"\n")
