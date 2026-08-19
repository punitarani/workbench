"""The per-run SQLite store: transactional steps, durable queue, snapshots."""

import sqlite3
from pathlib import Path

import pytest
from worldlog_fixtures import coherent_events

from core.events import EventDraft
from core.events.chat import ChatMessagePayload
from core.store import RunStoreError, SqliteRunStore


def draft(n: int) -> EventDraft:
    payload = ChatMessagePayload(
        kind="chat.message",
        chat_message_id=f"chm-9{n:05d}",
        conversation_id="cnv-000001",
        reply_to=None,
        sender="per-x",
        body=f"draft {n}",
    )
    return EventDraft(tag=payload.kind, source="gm", payload=payload)


def open_store(tmp_path: Path) -> SqliteRunStore:
    return SqliteRunStore.create(tmp_path / "run.db")


def test_events_round_trip_and_ordering(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    events = coherent_events()
    for event in events:
        store.append_event(event)
    store.commit()
    read_back = list(store.read_events())
    assert read_back == events
    assert store.head() == (len(events), int(events[-1].time))


def test_seq_gap_is_structurally_impossible(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    events = coherent_events()
    store.append_event(events[0])
    with pytest.raises(RunStoreError):
        store.append_event(events[2])  # skips seq 1


def test_commit_step_is_atomic(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    events = coherent_events()
    store.append_event(events[0])
    store.commit()
    store.queue_add(time=100, order=0, draft=draft(0))
    store.commit()

    class Boom(Exception):
        pass

    with pytest.raises(Boom):
        with store.transaction():
            store.append_event(events[1])
            store.queue_remove(order=0)
            store.queue_add(time=200, order=1, draft=draft(1))
            raise Boom()

    # Nothing from the failed transaction is visible.
    assert store.head() == (1, 0)
    assert [order for _, order, _ in store.queue_rows()] == [0]


def test_queue_rows_round_trip(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.queue_add(time=300, order=2, draft=draft(2))
    store.queue_add(time=100, order=0, draft=draft(0))
    store.commit()
    rows = store.queue_rows()
    assert [(t, o) for t, o, _ in rows] == [(100, 0), (300, 2)]
    assert rows[0][2].payload.body == "draft 0"


def test_snapshots_keep_latest(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.put_snapshot(step=3, taken_seq=10, state='{"a": 1}')
    store.put_snapshot(step=7, taken_seq=20, state='{"a": 2}')
    store.commit()
    latest = store.latest_snapshot()
    assert latest is not None
    assert latest.step == 7
    assert latest.state == '{"a": 2}'


def test_run_meta(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    store.set_meta("config_hash", "c" * 64)
    store.commit()
    assert store.get_meta("config_hash") == "c" * 64
    assert store.get_meta("missing") is None


def test_open_requires_existing_file(tmp_path: Path) -> None:
    with pytest.raises(RunStoreError):
        SqliteRunStore.open(tmp_path / "absent.db")


def test_reopen_sees_committed_state_only(tmp_path: Path) -> None:
    path = tmp_path / "run.db"
    store = SqliteRunStore.create(path)
    events = coherent_events()
    store.append_event(events[0])
    store.commit()
    store.append_event(events[1])  # uncommitted
    # Simulate a crash: reopen without commit via a second connection.
    crashed = sqlite3.connect(path)
    count = crashed.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    crashed.close()
    assert count == 1
    store.close()


def test_first_event_must_be_run_started(tmp_path: Path) -> None:
    store = open_store(tmp_path)
    stray = coherent_events()[10]
    rebased = stray.model_copy(update={"seq": 0, "event_id": "evt-000000"})
    with pytest.raises(RunStoreError):
        store.append_event(rebased)
