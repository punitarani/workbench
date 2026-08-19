"""Roll-forward resume: a run killed at ANY committed step resumes
byte-identically — no snapshot, a stale snapshot, or a fresh one."""

from pathlib import Path

from mini_workplace import make_spec
from test_dynamic_cast import IDLE_LM, arrival_spec
from test_workplace import (
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    SequenceLM,
)

from core.seed import Seed
from core.store import SqliteRunStore
from simulation.engine.engine import StopCondition
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.run import resume_workplace, run_workplace

CANNED = [
    DECIDE_IDLE_FALLBACK,
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    DECIDE_IDLE_FALLBACK,
]


async def _record_straight(tmp_path: Path, spec, canned) -> tuple[bytes, CassetteStore]:
    cassette = CassetteStore(tmp_path / "cassette")
    straight = tmp_path / "straight"
    await run_workplace(
        spec,
        seed=Seed(root=42),
        out_dir=straight,
        inner_lm=RecordingLM(SequenceLM(canned), cassette),
        model="test/model",
    )
    return (straight / "world.jsonl").read_bytes(), cassette


async def test_roll_forward_without_any_snapshot(tmp_path: Path) -> None:
    reference, cassette = await _record_straight(tmp_path, make_spec(), CANNED)

    out_dir = tmp_path / "split"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=2),
        checkpoint_every=1_000,
    )
    store = SqliteRunStore.open(out_dir / "run.db")
    assert store.latest_snapshot() is None, "the interrupt point has no snapshot"
    store.close()

    resumed = await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        checkpoint_every=1_000,
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == reference


async def test_roll_forward_from_stale_snapshot(tmp_path: Path) -> None:
    reference, cassette = await _record_straight(tmp_path, make_spec(), CANNED)

    out_dir = tmp_path / "split"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=3),
        checkpoint_every=2,
    )
    store = SqliteRunStore.open(out_dir / "run.db")
    stored = store.latest_snapshot()
    assert stored is not None and stored.taken_seq != store.head()[0], (
        "the snapshot is genuinely stale"
    )
    store.close()

    resumed = await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        checkpoint_every=2,
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == reference


async def test_arrival_roll_forward(tmp_path: Path) -> None:
    reference, cassette = await _record_straight(tmp_path, arrival_spec(), IDLE_LM)

    out_dir = tmp_path / "split"
    await run_workplace(
        arrival_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=10),
        checkpoint_every=1_000,
    )
    store = SqliteRunStore.open(out_dir / "run.db")
    assert store.latest_snapshot() is None
    arrived = any(
        event.tag == "person.record" and event.payload.person_id == "per-lena-brooks"
        for event in store.read_events()
    )
    store.close()
    assert arrived, "the interrupt point must fall after the arrival"

    resumed = await resume_workplace(
        arrival_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        checkpoint_every=1_000,
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == reference


async def test_graceful_interrupt_snapshots_at_head(tmp_path: Path) -> None:
    reference, cassette = await _record_straight(tmp_path, make_spec(), CANNED)

    out_dir = tmp_path / "sigint"
    seen = {"n": 0}

    def stop_after_two() -> bool:
        seen["n"] += 1
        return seen["n"] > 2

    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(stop_requested=stop_after_two),
        checkpoint_every=1_000,
    )
    assert result.reason == "interrupted"
    store = SqliteRunStore.open(out_dir / "run.db")
    stored = store.latest_snapshot()
    assert stored is not None and stored.taken_seq == store.head()[0], (
        "a graceful interrupt leaves a snapshot at the head"
    )
    store.close()

    resumed = await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == reference


async def test_snapshots_are_pruned(tmp_path: Path) -> None:
    _, cassette = await _record_straight(tmp_path, make_spec(), CANNED)
    out_dir = tmp_path / "dense"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        checkpoint_every=1,
    )
    store = SqliteRunStore.open(out_dir / "run.db")
    count = store._connection.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0]
    store.close()
    assert count <= 4, "dense checkpointing keeps a rolling set, not all"
