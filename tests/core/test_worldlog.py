from pathlib import Path

import pytest
from payload_samples import sample_payloads

from core.errors import WorldLogOrderingError
from core.events import Event
from core.worldlog import (
    RunManifest,
    WorldLogWriter,
    read_events,
    read_manifest,
    write_manifest,
)


def run_started_event(seq: int = 0, time: int = 0) -> Event:
    payload = sample_payloads()["sim.run.started"]
    return Event(seq=seq, time=time, tag=payload.kind, source="gm", payload=payload)


def chat_event(seq: int, time: int) -> Event:
    payload = sample_payloads()["chat.message"]
    return Event(seq=seq, time=time, tag=payload.kind, source="gm", payload=payload)


def test_append_and_read_round_trip(tmp_path: Path) -> None:
    log_path = tmp_path / "world.jsonl"
    with WorldLogWriter(log_path) as writer:
        writer.append(run_started_event())
        writer.append(chat_event(seq=1, time=60))
    events = read_events(log_path)
    assert [e.seq for e in events] == [0, 1]
    assert events[1].payload.kind == "chat.message"


def test_two_identical_writes_are_byte_identical(tmp_path: Path) -> None:
    paths = []
    for name in ("a.jsonl", "b.jsonl"):
        path = tmp_path / name
        with WorldLogWriter(path) as writer:
            writer.append(run_started_event())
            writer.append(chat_event(seq=1, time=60))
        paths.append(path)
    assert paths[0].read_bytes() == paths[1].read_bytes()


def test_first_event_must_be_run_started(tmp_path: Path) -> None:
    with WorldLogWriter(tmp_path / "w.jsonl") as writer:
        with pytest.raises(WorldLogOrderingError):
            writer.append(chat_event(seq=0, time=0))


def test_seq_must_be_gapless(tmp_path: Path) -> None:
    with WorldLogWriter(tmp_path / "w.jsonl") as writer:
        writer.append(run_started_event())
        with pytest.raises(WorldLogOrderingError):
            writer.append(chat_event(seq=3, time=60))


def test_time_must_not_regress(tmp_path: Path) -> None:
    with WorldLogWriter(tmp_path / "w.jsonl") as writer:
        writer.append(run_started_event(time=100))
        with pytest.raises(WorldLogOrderingError):
            writer.append(chat_event(seq=1, time=50))


def test_manifest_round_trip_and_sha(tmp_path: Path) -> None:
    log_path = tmp_path / "world.jsonl"
    with WorldLogWriter(log_path) as writer:
        writer.append(run_started_event())
    manifest = RunManifest.for_log(
        log_path,
        run_id="run-1",
        seed_root=42,
        workplace_id="legal-demo",
        config_hash="c" * 64,
    )
    assert manifest.event_count == 1
    manifest_path = tmp_path / "manifest.json"
    write_manifest(manifest, manifest_path)
    restored = read_manifest(manifest_path)
    assert restored == manifest
    log_path.write_bytes(log_path.read_bytes() + b" ")
    assert not restored.matches_log(log_path)
