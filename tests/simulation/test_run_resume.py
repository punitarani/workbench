"""Interrupt, resume, continue: a workplace run picks up where it stopped."""

from pathlib import Path

import pytest
from mini_workplace import make_spec
from test_workplace import (
    DECIDE_IDLE_FALLBACK,
    DECIDE_REPLY,
    DRAFT_REPLY,
    SequenceLM,
)

from workbench.core.seed import Seed
from workbench.simulation.engine.engine import StopCondition
from workbench.simulation.errors import ConfigMismatchError
from workbench.simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from workbench.simulation.run import resume_workplace, run_workplace


async def record_straight_run(tmp_path: Path) -> tuple[Path, CassetteStore]:
    cassette = CassetteStore(tmp_path / "cassette")
    out_dir = tmp_path / "straight"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=RecordingLM(
            SequenceLM(
                [
                    DECIDE_IDLE_FALLBACK,
                    DECIDE_IDLE_FALLBACK,
                    DECIDE_REPLY,
                    DRAFT_REPLY,
                    DECIDE_IDLE_FALLBACK,
                ]
            ),
            cassette,
        ),
        model="test/model",
    )
    return out_dir / "world.jsonl", cassette


async def test_run_writes_db_and_exports_identical_jsonl(tmp_path: Path) -> None:
    straight_log, _ = await record_straight_run(tmp_path)
    assert (straight_log.parent / "run.db").exists()
    assert straight_log.exists()


async def test_interrupt_then_resume_matches_straight(tmp_path: Path) -> None:
    straight_log, cassette = await record_straight_run(tmp_path)

    out_dir = tmp_path / "interrupted"
    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=1),
    )
    assert result.reason == "max_steps"

    resumed = await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == straight_log.read_bytes()


async def test_stop_requested_interrupts_cleanly(tmp_path: Path) -> None:
    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "sigint"

    calls = {"n": 0}

    def stop_after_first() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    result = await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(stop_requested=stop_after_first),
    )
    assert result.reason == "interrupted"

    resumed = await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
    assert resumed.reason == "quiescent"


async def test_resume_rejects_changed_config(tmp_path: Path) -> None:
    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "mismatch"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=1),
    )
    with pytest.raises(ConfigMismatchError):
        await resume_workplace(
            make_spec(end_of_day="16:00"),
            out_dir=out_dir,
            inner_lm=ReplayLM(cassette),
            model="test/model",
        )


async def test_double_resume_is_idempotent(tmp_path: Path) -> None:
    straight_log, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "double"
    await run_workplace(
        make_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=1),
    )
    first = await resume_workplace(
        make_spec(), out_dir=out_dir, inner_lm=ReplayLM(cassette), model="test/model"
    )
    assert first.reason == "quiescent"
    second = await resume_workplace(
        make_spec(), out_dir=out_dir, inner_lm=ReplayLM(cassette), model="test/model"
    )
    assert second.reason == "quiescent"
    assert second.steps == 0
    assert (out_dir / "world.jsonl").read_bytes() == straight_log.read_bytes()
