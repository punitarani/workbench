from pathlib import Path

import pytest
from toy_scenario import build_engine, resume_toy_engine

from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.errors import ConfigMismatchError, SnapshotError
from workbench.simulation.snapshot import (
    SimulationSnapshot,
    load_snapshot,
    save_snapshot,
    verify_resume,
)

CONFIG_HASH = "c" * 64


async def test_split_run_equals_straight_run(tmp_path: Path) -> None:
    straight_log = tmp_path / "straight.jsonl"
    engine, writer = build_engine(straight_log, max_messages=6)
    await engine.run(StopCondition(max_steps=6))
    writer.close()

    split_log = tmp_path / "split.jsonl"
    engine, writer = build_engine(split_log, max_messages=6)
    await engine.run(StopCondition(max_steps=3))
    snapshot = SimulationSnapshot(
        config_hash=CONFIG_HASH,
        seed_root=7,
        world_log_length=engine.next_seq,
        engine=engine.capture_state(),
    )
    writer.close()

    snapshot_path = tmp_path / "snap.json"
    save_snapshot(snapshot, snapshot_path)
    loaded = load_snapshot(snapshot_path)
    assert loaded == snapshot

    verify_resume(loaded, config_hash=CONFIG_HASH, log_path=split_log)
    resumed, resumed_writer = resume_toy_engine(split_log, loaded, max_messages=6)
    await resumed.run(StopCondition(max_steps=3))
    resumed_writer.close()

    assert split_log.read_bytes() == straight_log.read_bytes()


async def test_config_mismatch_refuses_resume(tmp_path: Path) -> None:
    log = tmp_path / "w.jsonl"
    engine, writer = build_engine(log)
    await engine.run(StopCondition(max_steps=2))
    snapshot = SimulationSnapshot(
        config_hash=CONFIG_HASH,
        seed_root=7,
        world_log_length=engine.next_seq,
        engine=engine.capture_state(),
    )
    writer.close()
    with pytest.raises(ConfigMismatchError):
        verify_resume(snapshot, config_hash="d" * 64, log_path=log)


async def test_log_length_mismatch_refuses_resume(tmp_path: Path) -> None:
    log = tmp_path / "w.jsonl"
    engine, writer = build_engine(log)
    await engine.run(StopCondition(max_steps=2))
    snapshot = SimulationSnapshot(
        config_hash=CONFIG_HASH,
        seed_root=7,
        world_log_length=engine.next_seq + 5,
        engine=engine.capture_state(),
    )
    writer.close()
    with pytest.raises(SnapshotError):
        verify_resume(snapshot, config_hash=CONFIG_HASH, log_path=log)


async def test_corrupt_schema_version_rejected(tmp_path: Path) -> None:
    log = tmp_path / "w.jsonl"
    engine, writer = build_engine(log)
    await engine.run(StopCondition(max_steps=1))
    snapshot = SimulationSnapshot(
        config_hash=CONFIG_HASH,
        seed_root=7,
        world_log_length=engine.next_seq,
        engine=engine.capture_state(),
    )
    writer.close()
    path = tmp_path / "snap.json"
    save_snapshot(snapshot, path)
    corrupted = path.read_text().replace('"schema_version": 1', '"schema_version": 99')
    path.write_text(corrupted)
    with pytest.raises(SnapshotError):
        load_snapshot(path)
