"""Scripted arrivals: new people (and their personas) join a running world."""

from pathlib import Path

from mini_workplace import ann_params, make_spec
from test_workplace import DECIDE_IDLE_FALLBACK, SequenceLM

from core.seed import Seed
from core.worldlog import read_events, validate_events
from simulation.engine.engine import StopCondition
from simulation.lm.cassette import CassetteStore, RecordingLM, ReplayLM
from simulation.run import resume_workplace, run_workplace
from simulation.workplace.compile import compile_workplace
from simulation.workplace.spec import (
    ExogenousEmail,
    OrganizationSpec,
    PersonArrival,
    PersonSpec,
)

IDLE_LM = [DECIDE_IDLE_FALLBACK]


def lena_spec() -> PersonSpec:
    params = ann_params().model_copy(
        update={"person_id": "per-lena-brooks", "name": "Lena Brooks"}
    )
    return PersonSpec(
        person_id="per-lena-brooks",
        name="Lena Brooks",
        email_address="lena@mini.example",
        title="Associate",
        department="Legal",
        manager=None,
        affiliation="internal",
        persona=params,
    )


def arrival_spec():
    return make_spec(
        organizations=(
            OrganizationSpec(
                org_id="org-000001", name="Acme Supplies", category="vendor"
            ),
        ),
        arrivals=(PersonArrival(at="09:20", person=lena_spec()),),
        day_script=(
            ExogenousEmail(
                at="09:40",
                sender="per-ravi-dee",
                to=("per-ann-liu",),
                cc=(),
                subject="Quick question",
                body="Can you confirm receipt?",
            ),
            ExogenousEmail(
                at="10:00",
                sender="per-ravi-dee",
                to=("per-lena-brooks",),
                cc=(),
                subject="Welcome aboard",
                body="Could you acknowledge this note?",
            ),
        ),
    )


def test_compile_schedules_arrival_and_org_genesis() -> None:
    compiled = compile_workplace(arrival_spec(), Seed(root=42))
    assert any(e.payload.kind == "org.record" for e in compiled.genesis)
    arrival_drafts = [
        item for item in compiled.scheduled if item.draft.tag == "person.record"
    ]
    assert len(arrival_drafts) == 1
    assert arrival_drafts[0].time == 9 * 3600 + 20 * 60
    assert ("lena-brooks",) == tuple(e for e, _ in compiled.arrivals)


async def test_arrival_joins_acts_and_log_validates(tmp_path: Path) -> None:
    out_dir = tmp_path / "run"
    result = await run_workplace(
        arrival_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=SequenceLM(IDLE_LM),
        model="test/model",
    )
    assert result.reason == "quiescent"
    events = read_events(out_dir / "world.jsonl")
    report = validate_events(events)
    assert report.ok, report.findings

    arrival = next(
        e
        for e in events
        if e.tag == "person.record" and e.payload.person_id == "per-lena-brooks"
    )
    welcome = next(
        e for e in events if e.tag == "email.message" and "Welcome" in e.payload.subject
    )
    assert arrival.seq < welcome.seq
    # Lena observed her welcome mail and got an acting turn (idle) without
    # any grounding rejection.
    notes = [e for e in events if e.tag == "sim.gm.note"]
    assert notes == [], [n.payload.note for n in notes]


async def test_resume_after_arrival_matches_straight(tmp_path: Path) -> None:
    cassette = CassetteStore(tmp_path / "cassette")
    straight_dir = tmp_path / "straight"
    await run_workplace(
        arrival_spec(),
        seed=Seed(root=42),
        out_dir=straight_dir,
        inner_lm=RecordingLM(SequenceLM(IDLE_LM), cassette),
        model="test/model",
    )

    out_dir = tmp_path / "split"
    await run_workplace(
        arrival_spec(),
        seed=Seed(root=42),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
        stop=StopCondition(max_steps=8),
    )
    resumed = await resume_workplace(
        arrival_spec(),
        out_dir=out_dir,
        inner_lm=ReplayLM(cassette),
        model="test/model",
    )
    assert resumed.reason == "quiescent"
    assert (out_dir / "world.jsonl").read_bytes() == (
        straight_dir / "world.jsonl"
    ).read_bytes()
