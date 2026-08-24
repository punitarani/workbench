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

from core.seed import Seed
from core.store import SqliteRunStore
from simulation.engine.engine import StopCondition
from simulation.errors import ConfigMismatchError
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.run import engine_fingerprint, resume_workplace, run_workplace


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


async def test_a_run_stores_its_engine_fingerprint(tmp_path: Path) -> None:
    """The write, without which the refusal below can never fire.

    `resume_workplace` guards on `if stored_engine and stored_engine !=
    current_engine`, so a run that never records one resumes under any
    rules at all, silently and forever. Deleting the single `set_meta` line
    left the whole suite green until this test existed.
    """

    _, cassette = await record_straight_run(tmp_path)
    store = SqliteRunStore.open(tmp_path / "straight" / "run.db")
    stored = store.get_meta("engine_fingerprint")
    store.close()
    assert stored, "a recording that stores no fingerprint cannot be protected"
    assert stored == engine_fingerprint()


async def test_resume_refuses_after_the_grounding_rules_change(
    tmp_path: Path,
) -> None:
    """The gate itself, which five tests of the fingerprint did not cover.

    `config_hash` covers *what world* is being recorded and nothing about
    *how*, so a long run can be stopped, the referee edited, and resumed --
    flat for forty days and nested afterwards, with nothing in the log
    saying where the seam is. That happened here at day 4 of a 130-workday
    run and only an unrelated stop kept the world uniform.

    Mutating the comparison to `if False:` left 376 tests passing.
    """

    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "straight"
    store = SqliteRunStore.open(out_dir / "run.db")
    store.set_meta("engine_fingerprint", "0" * 64)
    store.commit()
    store.close()

    with pytest.raises(ConfigMismatchError, match="grounding rules changed"):
        await resume_workplace(
            make_spec(),
            out_dir=out_dir,
            inner_lm=ReplayLM(cassette),
            model="test/model",
        )


async def test_the_refusal_names_both_fingerprints(tmp_path: Path) -> None:
    """A refusal that does not say what changed sends someone guessing.

    Twelve characters of each is enough to tell two recordings apart in a
    directory listing and short enough to read aloud.
    """

    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "straight"
    store = SqliteRunStore.open(out_dir / "run.db")
    store.set_meta("engine_fingerprint", "a" * 64)
    store.commit()
    store.close()

    with pytest.raises(ConfigMismatchError) as raised:
        await resume_workplace(
            make_spec(),
            out_dir=out_dir,
            inner_lm=ReplayLM(cassette),
            model="test/model",
        )
    message = str(raised.value)
    assert "a" * 12 in message
    assert engine_fingerprint()[:12] in message


async def test_allow_engine_change_is_the_documented_way_past(
    tmp_path: Path,
) -> None:
    """The escape hatch the refusal names, so it must actually work.

    A gate whose stated remedy does not function is worse than no gate: the
    next person edits the guard instead.
    """

    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "straight"
    store = SqliteRunStore.open(out_dir / "run.db")
    store.set_meta("engine_fingerprint", "b" * 64)
    store.commit()
    store.close()

    await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        allow_engine_change=True,
    )


async def test_a_run_without_a_stored_fingerprint_still_resumes(
    tmp_path: Path,
) -> None:
    """`stored_engine and ...` is deliberate, not an oversight.

    A run.db recorded before the fingerprint existed has no value to
    compare, and refusing those would strand every earlier recording. The
    guard reads "if we know what it was recorded under"; this pins that
    reading so nobody tightens it into a refusal.
    """

    _, cassette = await record_straight_run(tmp_path)
    out_dir = tmp_path / "straight"
    store = SqliteRunStore.open(out_dir / "run.db")
    store.set_meta("engine_fingerprint", "")
    store.commit()
    store.close()

    await resume_workplace(
        make_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
