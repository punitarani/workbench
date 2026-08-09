"""Full-day acceptance for the legal demo.

Needs the recorded cassette committed at CASSETTE below. Record it once:

    OPENROUTER_API_KEY=... uv run python -m workbench.simulation.demo \
        --seed 42 --mode record --out out/legal-day-record \
        --cassette workplaces/src/workbench/workplaces/legal/cassettes/day-seed42

Until then every test here skips; the structural suite in
test_legal_workplace.py runs regardless.
"""

import os
from pathlib import Path

import pytest

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.audit.heuristics import (
    register_matches_channel,
    replies_address_their_threads,
    unwritten_standard_litmus,
)
from workbench.simulation.lm.cassette import CassetteStore, ReplayLM
from workbench.simulation.run import run_workplace
from workbench.workplaces.legal import UNWRITTEN_STANDARD_PHRASES, WORKPLACE

CASSETTE = (
    Path(__file__).parent.parent
    / "src"
    / "workbench"
    / "workplaces"
    / "legal"
    / "cassettes"
    / "day-seed42"
)

pytestmark = pytest.mark.skipif(
    not CASSETTE.exists() or not any(CASSETTE.glob("*.json")),
    reason="demo cassette not recorded yet; see module docstring",
)

MIN_EVENTS = 60
CHANNEL_MINIMUMS = {
    "email.message": 15,
    "chat.message": 20,
    "ticket.": 5,
    "document.revised": 2,
    "calendar.": 2,
}


async def replay(tmp_path: Path, name: str) -> Path:
    out_dir = tmp_path / name
    await run_workplace(
        WORKPLACE,
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(CassetteStore(CASSETTE)),
        model="deepseek/deepseek-v4-flash-0731",
    )
    return out_dir / "world.jsonl"


async def test_replay_is_byte_identical(tmp_path: Path) -> None:
    first = await replay(tmp_path, "a")
    second = await replay(tmp_path, "b")
    assert first.read_bytes() == second.read_bytes()


async def test_log_validates_with_zero_errors(tmp_path: Path) -> None:
    events = read_events(await replay(tmp_path, "v"))
    report = validate_events(events)
    assert report.ok, report.findings


async def test_volume_and_coverage(tmp_path: Path) -> None:
    events = read_events(await replay(tmp_path, "vol"))
    real = [e for e in events if not e.tag.startswith("sim.")]
    assert len(real) >= MIN_EVENTS
    for prefix, minimum in CHANNEL_MINIMUMS.items():
        count = sum(1 for e in real if e.tag.startswith(prefix))
        assert count >= minimum, f"{prefix}: {count} < {minimum}"
    internal = {p.person_id for p in WORKPLACE.people if p.persona is not None}
    for person in internal:
        authored = sum(
            1
            for e in real
            if getattr(e.payload, "sender", getattr(e.payload, "actor", None))
            == person
        )
        assert authored >= 3, f"{person} authored only {authored} events"


async def test_storyline_milestones_in_causal_order(tmp_path: Path) -> None:
    events = read_events(await replay(tmp_path, "story"))
    nda_email = next(
        e
        for e in events
        if e.tag == "email.message" and "Vantage" in e.payload.subject
    )
    ticket = next(
        e for e in events if e.tag == "ticket.created" and e.seq > nda_email.seq
    )
    statement = next(
        e
        for e in events
        if e.tag in ("chat.message", "email.message")
        and e.payload.sender == "per-daniel-reyes"
        and any(
            p.casefold() in e.payload.body.casefold()
            for p in UNWRITTEN_STANDARD_PHRASES
        )
    )
    revision = next(
        e for e in events if e.tag == "document.revised" and e.seq > statement.seq
    )
    reply = next(
        e
        for e in events
        if e.tag == "email.message"
        and e.seq > revision.seq
        and e.payload.thread_id == nda_email.payload.thread_id
    )
    assert nda_email.seq < ticket.seq < statement.seq < revision.seq < reply.seq


async def test_litmus_and_heuristics(tmp_path: Path) -> None:
    events = read_events(await replay(tmp_path, "aud"))
    passed_any = False
    for phrase in UNWRITTEN_STANDARD_PHRASES:
        result = unwritten_standard_litmus(
            events, phrase=phrase, holder="per-daniel-reyes"
        )
        passed_any = passed_any or result.passed
    assert passed_any, "no unwritten-standard phrase flowed person->artifact"
    assert replies_address_their_threads(events) == ()
    assert register_matches_channel(events) == ()


@pytest.mark.real_lm
@pytest.mark.skipif(
    not os.environ.get("WORKBENCH_REAL_LM"),
    reason="set WORKBENCH_REAL_LM=1 and OPENROUTER_API_KEY to run",
)
async def test_real_model_smoke(tmp_path: Path) -> None:
    from workbench.simulation.lm.budget import BudgetedLM
    from workbench.simulation.lm.cassette import RecordingLM
    from workbench.simulation.lm.openrouter import OpenRouterLM

    backend = OpenRouterLM(api_key=os.environ["OPENROUTER_API_KEY"])
    inner = BudgetedLM(
        RecordingLM(backend, CassetteStore(tmp_path / "cassette")),
        max_calls=60,
    )
    out_dir = tmp_path / "smoke"
    from workbench.simulation.engine.engine import StopCondition

    await run_workplace(
        WORKPLACE,
        seed=Seed(root=7),
        out_dir=out_dir,
        inner_lm=inner,
        model="deepseek/deepseek-v4-flash-0731",
        stop=StopCondition(max_steps=8),
    )
    events = read_events(out_dir / "world.jsonl")
    report = validate_events(events)
    assert report.ok, report.findings
    assert any(e.tag == "email.message" for e in events)
