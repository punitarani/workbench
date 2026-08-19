"""Hybrid start: the engine continues a world that already has history."""

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mini_workplace import make_spec
from test_workplace import (
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    SequenceLM,
)

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.chronicle.minter import minter_from_events
from simulation.run import run_compiled, run_workplace
from simulation.workplace.compile import compile_workplace

CANNED = [
    DECIDE_IDLE_FALLBACK,
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    DECIDE_IDLE_FALLBACK,
]

DAY_TWO_EPOCH = datetime(2026, 3, 13, 0, 0, tzinfo=ZoneInfo("UTC"))


async def test_engine_continues_from_existing_history(tmp_path: Path) -> None:
    # Day one: an ordinary run producing a complete world log.
    day_one = tmp_path / "day-one"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=day_one,
        inner_lm=SequenceLM(CANNED),
        model="test/model",
    )
    history = read_events(day_one / "world.jsonl")
    assert validate_events(history).ok

    # Day two: same cast, no genesis (the world already exists), the whole
    # schedule shifted one calendar day, ids continuing from the history.
    spec_two = make_spec(epoch=DAY_TWO_EPOCH)
    compiled = compile_workplace(
        spec_two,
        Seed(root=42),
        time_offset=86_400,
        starting_minter=minter_from_events(history),
        include_genesis=False,
    )
    assert compiled.genesis == ()
    assert all(item.time >= 86_400 for item in compiled.scheduled)

    day_two = tmp_path / "day-two"
    result = await run_compiled(
        compiled,
        seed=Seed(root=42),
        out_dir=day_two,
        inner_lm=SequenceLM(CANNED),
        model="test/model",
        history=tuple(history),
    )
    assert result.reason == "quiescent"

    combined = read_events(day_two / "world.jsonl")
    report = validate_events(combined)
    assert report.ok, report.findings

    assert combined[: len(history)] == list(history), (
        "the continued log preserves history byte-for-byte"
    )
    new_events = combined[len(history) :]
    assert new_events, "day two produced activity"
    assert all(int(e.time) >= 86_400 for e in new_events)

    day_one_ids = {e.payload.message_id for e in history if e.tag == "email.message"}
    day_two_ids = {e.payload.message_id for e in new_events if e.tag == "email.message"}
    assert not day_one_ids & day_two_ids, "minted ids never collide with history"
