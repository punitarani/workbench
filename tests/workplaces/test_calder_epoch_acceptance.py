"""Acceptance for the LLM-first Calder epoch: the recorded two-day run
replays byte-identically — sequential, windowed, and killed-then-resumed
at an arbitrary step. Activates when the local cassette exists."""

from pathlib import Path

import pytest

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.engine.engine import StopCondition
from simulation.lm.cassette import CassetteStore, ReplayLM
from simulation.run import resume_workplace, run_compiled
from simulation.workplace.compile import compile_workplace
from workplaces.calder.epoch import epoch_director, epoch_spec

CASSETTE = Path(__file__).parents[2] / "src/workplaces/calder/cassettes/epoch-seed42"
FAST = "deepseek/deepseek-v4-flash-0731"
DEEP = "anthropic/claude-haiku-4.5"
SEED = Seed(root=42)
DAYS = 2

pytestmark = pytest.mark.skipif(
    not CASSETTE.exists(), reason="calder epoch cassette is not recorded"
)


async def _replay(tmp_path: Path, *, name: str, window: int, max_steps=None):
    spec = epoch_spec(days=DAYS)
    compiled = compile_workplace(spec, SEED)
    out_dir = tmp_path / name
    result = await run_compiled(
        compiled,
        seed=SEED,
        out_dir=out_dir,
        inner_lm=ReplayLM(CassetteStore(CASSETTE)),
        model=FAST,
        deep_model=DEEP,
        director=epoch_director(SEED),
        stop=StopCondition(end_time=compiled.end_time, max_steps=max_steps),
        checkpoint_every=100,
        window=window,
    )
    return result, out_dir


async def test_epoch_replay_windows_and_kill_anywhere(tmp_path: Path) -> None:
    straight, straight_dir = await _replay(tmp_path, name="straight", window=1)
    reference = (straight_dir / "world.jsonl").read_bytes()
    events = tuple(read_events(straight_dir / "world.jsonl"))
    assert validate_events(events).ok
    tags = {event.tag for event in events}
    assert {
        "sim.agent.plan",
        "sim.agent.memory",
        "meeting.transcript",
        "sim.cue",
        "email.message",
    } <= tags, "the epoch day carries the full cognition surface"

    windowed, windowed_dir = await _replay(tmp_path, name="windowed", window=32)
    assert (windowed_dir / "world.jsonl").read_bytes() == reference
    assert windowed.steps == straight.steps

    # Kill at an arbitrary (non-checkpoint) step; roll-forward resumes.
    interrupted, split_dir = await _replay(
        tmp_path, name="split", window=1, max_steps=73
    )
    assert interrupted.reason == "max_steps"
    spec = epoch_spec(days=DAYS)
    compiled = compile_workplace(spec, SEED)
    resumed = await resume_workplace(
        spec,
        out_dir=split_dir,
        inner_lm=ReplayLM(CassetteStore(CASSETTE)),
        model=FAST,
        deep_model=DEEP,
        director=epoch_director(SEED),
        stop=StopCondition(end_time=compiled.end_time),
        checkpoint_every=100,
    )
    assert interrupted.steps + resumed.steps == straight.steps
    assert (split_dir / "world.jsonl").read_bytes() == reference
