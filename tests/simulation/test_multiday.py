"""Multi-day simulation: day chains, workday wake ladders, cross-day resume."""

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

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from workbench.simulation.run import resume_workplace, run_workplace
from workbench.simulation.workplace.compile import compile_workplace

CANNED = [
    DECIDE_IDLE_FALLBACK,
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    DECIDE_IDLE_FALLBACK,
]

# 2026-03-13 is a Friday: day 0 = Fri, 1 = Sat, 2 = Sun, 3 = Mon.
FRIDAY_EPOCH = datetime(2026, 3, 13, 0, 0, tzinfo=ZoneInfo("UTC"))


def multi_spec(days: int = 4):
    return make_spec(epoch=FRIDAY_EPOCH, days=days)


def test_single_day_goes_through_the_day_chain() -> None:
    """COMPILER v2: days=1 unfolds exactly like any other day — one
    sim.day.started compiled, wake cohorts minted at runtime."""
    compiled = compile_workplace(make_spec(), Seed(root=42))
    tags = [item.draft.tag for item in compiled.scheduled]
    assert tags.count("sim.day.started") == 1
    assert "sim.wake" not in tags


def test_multiday_compile_schedules_only_day_zero_start() -> None:
    compiled = compile_workplace(multi_spec(), Seed(root=42))
    assert [
        item.draft.tag
        for item in compiled.scheduled
        if item.draft.tag.startswith("sim.day")
    ] == ["sim.day.started"]
    assert all(item.draft.tag != "sim.wake" for item in compiled.scheduled), (
        "multi-day wakes are minted at runtime by the day chain"
    )
    assert compiled.end_time == 3 * 86400 + 17 * 3600 + 30 * 60


async def run_days(tmp_path: Path, name: str, inner_lm) -> Path:
    out_dir = tmp_path / name
    await run_workplace(
        multi_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=inner_lm,
        model="test/model",
    )
    return out_dir / "world.jsonl"


async def test_day_chain_skips_weekend_and_ladders_workdays(tmp_path: Path) -> None:
    log = await run_days(tmp_path, "chain", SequenceLM(CANNED))
    events = read_events(log)
    report = validate_events(events)
    assert report.ok, report.findings

    day_started = [e.payload.day for e in events if e.tag == "sim.day.started"]
    day_ended = [e.payload.day for e in events if e.tag == "sim.day.ended"]
    assert day_started == ["2026-03-13", "2026-03-16"], "Sat/Sun are skipped"
    assert day_ended == ["2026-03-13", "2026-03-16"]

    wakes = [e for e in events if e.tag == "sim.wake"]
    friday_wakes = [e for e in wakes if int(e.time) < 86400]
    monday_wakes = [e for e in wakes if int(e.time) >= 3 * 86400]
    assert len(friday_wakes) == len(monday_wakes) > 0
    assert len(friday_wakes) + len(monday_wakes) == len(wakes)
    # Cohort grid: every wake lands on a 30-minute tick at or after 09:00.
    grid = 30 * 60
    for wake in wakes:
        clock = int(wake.time) % 86_400
        assert clock >= 9 * 3600
        assert (clock - 9 * 3600) % grid == 0, "wakes land on grid ticks"


async def test_multiday_is_deterministic(tmp_path: Path) -> None:
    first = await run_days(tmp_path, "a", SequenceLM(CANNED))
    second = await run_days(tmp_path, "b", SequenceLM(CANNED))
    assert first.read_bytes() == second.read_bytes()


async def test_resume_across_day_boundary(tmp_path: Path) -> None:
    cassette = CassetteStore(tmp_path / "cassette")
    straight = await run_days(
        tmp_path, "straight", RecordingLM(SequenceLM(CANNED), cassette)
    )

    out_dir = tmp_path / "split"
    # Interrupt on Friday afternoon, well before the Monday segment.
    await run_workplace(
        multi_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=6),
    )
    resumed = await resume_workplace(
        multi_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == straight.read_bytes()
