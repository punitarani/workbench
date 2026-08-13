from pathlib import Path

from toy_scenario import build_engine

from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.engine.engine import StopCondition


async def run_toy(tmp_path: Path, name: str = "world.jsonl") -> Path:
    log_path = tmp_path / name
    engine, writer = build_engine(log_path)
    try:
        await engine.run(StopCondition(max_steps=20))
    finally:
        writer.close()
    return log_path


async def test_step_anatomy(tmp_path: Path) -> None:
    engine, writer = build_engine(tmp_path / "world.jsonl")
    try:
        result = await engine.step()
    finally:
        writer.close()
    assert result.step == 0
    assert result.event.payload.kind == "chat.message"
    assert result.event.source == "ann"
    assert result.event.seq == 5, "genesis is seq 0-4, first step mints 5"
    assert result.observers == ("bob", "cat"), "sender does not observe itself"
    assert [entity for entity, _ in result.actions] == ["bob"]
    assert len(result.scheduled) == 1


async def test_full_run_produces_valid_terminating_log(tmp_path: Path) -> None:
    log_path = tmp_path / "world.jsonl"
    engine, writer = build_engine(log_path)
    try:
        result = await engine.run(StopCondition(max_steps=20))
    finally:
        writer.close()
    assert result.reason == "terminated"
    events = read_events(log_path)
    chat_messages = [e for e in events if e.payload.kind == "chat.message"]
    assert len(chat_messages) == 4
    report = validate_events(events)
    assert report.ok, report.findings
    assert chat_messages[1].payload.body == "bob heard: kickoff"
    assert chat_messages[2].payload.body == "cat heard: bob heard: kickoff"
    assert chat_messages[1].caused_by == chat_messages[0].event_id


async def test_same_build_twice_is_byte_identical(tmp_path: Path) -> None:
    first = await run_toy(tmp_path, "a.jsonl")
    second = await run_toy(tmp_path, "b.jsonl")
    assert first.read_bytes() == second.read_bytes()


async def test_quiescent_queue_ends_run(tmp_path: Path) -> None:
    engine, writer = build_engine(tmp_path / "world.jsonl", max_messages=100)
    try:
        result = await engine.run(StopCondition(max_steps=3))
    finally:
        writer.close()
    assert result.reason == "max_steps"
    assert result.steps == 3


def test_run_is_pythonhashseed_independent(tmp_path: Path) -> None:
    import subprocess
    import sys

    tests_dir = Path(__file__).parent
    code = (
        "import asyncio, hashlib, sys, tempfile\n"
        f"sys.path.insert(0, {str(tests_dir)!r})\n"
        "from pathlib import Path\n"
        "from toy_scenario import build_engine\n"
        "from workbench.simulation.engine.engine import StopCondition\n"
        "async def main():\n"
        "    with tempfile.TemporaryDirectory() as d:\n"
        "        p = Path(d) / 'w.jsonl'\n"
        "        engine, writer = build_engine(p)\n"
        "        await engine.run(StopCondition(max_steps=20))\n"
        "        writer.close()\n"
        "        print(hashlib.sha256(p.read_bytes()).hexdigest())\n"
        "asyncio.run(main())\n"
    )
    digests = set()
    for hash_seed in ("0", "42"):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": hash_seed, "PATH": "/usr/bin:/bin"},
        )
        digests.add(completed.stdout.strip())
    assert len(digests) == 1, digests
