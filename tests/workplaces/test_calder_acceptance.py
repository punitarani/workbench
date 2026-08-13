"""Acceptance for the Calder live day: the committed cassette replays the
recorded day byte-identically — sequential, windowed, and split by an
interrupt — on top of a history the test rebuilds from scratch.

The six-month chronicle is byte-deterministic and takes about a second to
build, so this test is self-contained: no network, no pre-built out/.
Activates only when the cassette directory exists.
"""

import importlib.util
from pathlib import Path

import pytest

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.chronicle.minter import minter_from_events
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.lm.cassette import CassetteStore, ReplayLM
from workbench.simulation.run import resume_workplace, run_compiled
from workbench.simulation.workplace.compile import compile_workplace
from workbench.workplaces.calder import LIVE_DAY_OFFSET
from workbench.workplaces.calder.spec import LIVE_DAY_SPEC

CASSETTE = (
    Path(__file__).parents[2]
    / "src/workbench/workplaces/calder/cassettes/live-2026-07-20"
)
MODEL = "deepseek/deepseek-v4-flash-0731"
SEED = Seed(root=42)
CHECKPOINT_EVERY = 50

pytestmark = pytest.mark.skipif(
    not CASSETTE.exists(), reason="calder live-day cassette is not recorded"
)

_SPEC = importlib.util.spec_from_file_location(
    "calder_build_for_acceptance",
    Path(__file__).parents[2] / "datasets" / "calder" / "build_history.py",
)
_build_history = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_build_history)


def _history(tmp_path: Path) -> tuple:
    log_path = _build_history.build_world(tmp_path / "history", SEED, day_count=None)
    return tuple(read_events(log_path))


async def _replay(
    tmp_path: Path,
    history: tuple,
    *,
    name: str,
    window: int,
    max_steps: int | None = None,
):
    compiled = compile_workplace(
        LIVE_DAY_SPEC,
        SEED,
        time_offset=LIVE_DAY_OFFSET,
        starting_minter=minter_from_events(history),
        include_genesis=False,
    )
    out_dir = tmp_path / name
    result = await run_compiled(
        compiled,
        seed=SEED,
        out_dir=out_dir,
        inner_lm=ReplayLM(CassetteStore(CASSETTE)),
        model=MODEL,
        stop=StopCondition(end_time=compiled.end_time, max_steps=max_steps),
        history=history,
        checkpoint_every=CHECKPOINT_EVERY,
        window=window,
    )
    return result, out_dir


async def test_live_day_replay_windows_and_resume(tmp_path: Path) -> None:
    history = _history(tmp_path)

    straight, straight_dir = await _replay(tmp_path, history, name="straight", window=1)
    reference = (straight_dir / "world.jsonl").read_bytes()
    combined = tuple(read_events(straight_dir / "world.jsonl"))
    assert validate_events(combined).ok
    new_events = len(combined) - len(history)
    assert new_events > 100, "the live day carries a real day's traffic"
    assert straight.reason in ("quiescent", "end_of_day", "time")

    windowed, windowed_dir = await _replay(tmp_path, history, name="windowed", window=8)
    assert (windowed_dir / "world.jsonl").read_bytes() == reference, (
        "window=8 must replay byte-identically to sequential"
    )
    assert windowed.steps == straight.steps

    interrupted, split_dir = await _replay(
        tmp_path, history, name="split", window=1, max_steps=CHECKPOINT_EVERY
    )
    assert interrupted.reason == "max_steps"
    # Resume needs the absolute stop: recompiling without the hybrid
    # offset would place end-of-day back on day zero.
    end_time = LIVE_DAY_OFFSET + 17 * 3600 + 1800
    resumed = await resume_workplace(
        LIVE_DAY_SPEC,
        out_dir=split_dir,
        inner_lm=ReplayLM(CassetteStore(CASSETTE)),
        model=MODEL,
        stop=StopCondition(end_time=end_time),
        checkpoint_every=CHECKPOINT_EVERY,
    )
    assert interrupted.steps + resumed.steps == straight.steps
    assert (split_dir / "world.jsonl").read_bytes() == reference, (
        "interrupt + resume must reproduce the straight run byte for byte"
    )
