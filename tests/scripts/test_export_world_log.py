"""The world log must be recoverable from a run that did not finish.

`export_jsonl` had exactly one caller — `simulation.run._finish`, which
runs when a recording *completes*. A six-month recording takes about a
day, and every downstream step reads `world.jsonl` while none of them
reads `run.db`. So an interrupt at hour twenty-three left every event
safely stored and not one of them reachable: the Merrick v2 recording was
stopped at day 40 of 130 and had an 18MB store and no world log.

Correct code, one caller, and the caller on the happy path. This is the
same shape as the defects in
tests/simulation/test_engine_failures_are_not_world_data.py, in
operational clothes.
"""

import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
# `scripts/` because that is where the thing under test lives, and
# `tests/simulation/` for `toy_scenario`, whose store-backed engine is the
# only fixture in the tree that produces a real run store.
sys.path.insert(0, str(_ROOT / "scripts"))
sys.path.insert(0, str(_ROOT / "tests" / "simulation"))

from toy_scenario import build_store_engine  # noqa: E402

from core.worldlog import read_events  # noqa: E402
from core.worldlog.validate import validate_events  # noqa: E402
from export_world_log import export  # noqa: E402
from simulation.engine.engine import StopCondition  # noqa: E402


async def _partial_run(out_dir: Path, steps: int = 20):
    """A store with events in it and no world log — an interrupted run."""

    out_dir.mkdir(parents=True, exist_ok=True)
    engine, store = build_store_engine(out_dir / "run.db")
    await engine.run(StopCondition(max_steps=steps))
    # What a real recording writes into run_meta. Without it the export
    # refuses, which is its own test below.
    store.set_meta("workplace_id", "merrick")
    store.set_meta("seed_root", "42")
    store.set_meta("config_hash", "c0ffee" * 10)
    store.set_meta("engine_fingerprint", "1ec4c4ac" * 8)
    store.commit()
    store.close()
    assert not (out_dir / "world.jsonl").exists(), (
        "fixture is not testing recovery: the run already wrote a log"
    )


async def test_an_unfinished_run_still_yields_a_valid_world_log(tmp_path: Path) -> None:
    out = tmp_path / "epoch"
    await _partial_run(out)

    export(out)

    log = out / "world.jsonl"
    events = tuple(read_events(log))
    assert events, "exported an empty log from a store with events in it"
    assert validate_events(events).ok, "the recovered log does not validate"
    assert (out / "manifest.json").is_file()


async def test_the_manifest_counts_what_the_log_holds(tmp_path: Path) -> None:
    import json

    out = tmp_path / "epoch"
    await _partial_run(out)
    export(out)

    manifest = json.loads((out / "manifest.json").read_text())
    lines = [
        line
        for line in (out / "world.jsonl").read_bytes().splitlines()
        if line.strip()
    ]
    assert manifest["event_count"] == len(lines)
    # Identity comes from the store, never from a flag or the directory
    # name: an export labelled with the wrong workplace or seed is worse
    # than no export, because it looks authoritative.
    assert manifest["seed_root"] == 42
    assert manifest["workplace_id"]


async def test_it_refuses_to_overwrite_a_finished_export(tmp_path: Path) -> None:
    """Re-running it must not quietly replace a complete log with a partial one."""

    out = tmp_path / "epoch"
    await _partial_run(out)
    export(out)
    before = (out / "world.jsonl").read_bytes()

    with pytest.raises(SystemExit):
        export(out)
    assert (out / "world.jsonl").read_bytes() == before

    export(out, force=True)
    assert (out / "world.jsonl").read_bytes() == before


async def test_it_refuses_a_directory_with_no_store(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        export(tmp_path / "nothing-here")


async def test_it_refuses_a_store_with_no_run_identity(tmp_path: Path) -> None:
    """A store that is not a recording gets no manifest at all.

    Guessing `workplace_id` from the directory name and `seed_root` from
    nothing produces a manifest that is confident, wrong, and indistinguishable
    from a real one.
    """

    out = tmp_path / "epoch"
    out.mkdir()
    engine, store = build_store_engine(out / "run.db")
    await engine.run(StopCondition(max_steps=5))
    store.close()

    with pytest.raises(SystemExit, match="no run identity"):
        export(out)
    assert not (out / "manifest.json").exists()
