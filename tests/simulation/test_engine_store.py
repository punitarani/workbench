"""Engine + run store: end-of-step atomic commit, crash-equivalent recovery."""

from pathlib import Path

import pytest
from toy_scenario import build_engine, build_store_engine, resume_store_engine

from core.store import SqliteRunStore, export_jsonl
from simulation.engine.engine import StopCondition


async def test_store_run_exports_byte_identical_log(tmp_path: Path) -> None:
    jsonl_path = tmp_path / "writer.jsonl"
    engine, writer = build_engine(jsonl_path)
    await engine.run(StopCondition(max_steps=20))
    writer.close()

    store_path = tmp_path / "run.db"
    engine, store = build_store_engine(store_path)
    await engine.run(StopCondition(max_steps=20))
    exported = tmp_path / "exported.jsonl"
    export_jsonl(store, exported)
    store.close()

    assert exported.read_bytes() == jsonl_path.read_bytes()


async def test_interrupted_step_leaves_no_trace(tmp_path: Path) -> None:
    store_path = tmp_path / "run.db"
    engine, store = build_store_engine(store_path, explode_on_step=2)
    with pytest.raises(RuntimeError, match="boom"):
        await engine.run(StopCondition(max_steps=20))
    store.close()

    reopened = SqliteRunStore.open(store_path)
    events = list(reopened.read_events())
    # Genesis (5 events) plus exactly the two committed steps.
    committed_steps = [e for e in events if e.seq >= 5]
    assert len(committed_steps) == 2
    # The failed step's queue row survives for re-execution.
    orders = [order for _, order, _ in reopened.queue_rows()]
    assert orders, "the popped-but-uncommitted draft must still be queued"
    reopened.close()


async def test_resumed_store_run_matches_straight_run(tmp_path: Path) -> None:
    straight = tmp_path / "straight.db"
    engine, store = build_store_engine(straight)
    await engine.run(StopCondition(max_steps=20))
    straight_export = tmp_path / "straight.jsonl"
    export_jsonl(store, straight_export)
    store.close()

    crashed = tmp_path / "crashed.db"
    engine, store = build_store_engine(crashed, explode_on_step=2)
    with pytest.raises(RuntimeError):
        await engine.run(StopCondition(max_steps=20))
    store.close()

    resumed_store = SqliteRunStore.open(crashed)
    engine = await resume_store_engine(resumed_store)
    await engine.run(StopCondition(max_steps=20))
    resumed_export = tmp_path / "resumed.jsonl"
    export_jsonl(resumed_store, resumed_export)
    resumed_store.close()

    assert resumed_export.read_bytes() == straight_export.read_bytes()
