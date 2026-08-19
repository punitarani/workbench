"""The live-day spec compiles as a hybrid continuation: no genesis, the
whole schedule shifted onto the absolute timeline, every persona on the
wake ladder, and ids continuing past the history."""

import importlib.util
from pathlib import Path

from core.seed import Seed
from core.worldlog import read_events
from simulation.chronicle.minter import minter_from_events
from simulation.workplace.compile import compile_workplace
from workplaces.calder import LIVE_DAY_OFFSET
from workplaces.calder.people import ARRIVAL, EMPLOYEES
from workplaces.calder.spec import LIVE_DAY_SPEC

_SPEC = importlib.util.spec_from_file_location(
    "calder_build_for_spec_test",
    Path(__file__).parents[2] / "datasets" / "calder" / "build_history.py",
)
build_history = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(build_history)


def test_live_day_compiles_against_history(tmp_path: Path) -> None:
    log_path = build_history.build_world(tmp_path, Seed(root=42), day_count=12)
    history = tuple(read_events(log_path))

    compiled = compile_workplace(
        LIVE_DAY_SPEC,
        Seed(root=42),
        time_offset=LIVE_DAY_OFFSET,
        starting_minter=minter_from_events(history),
        include_genesis=False,
    )
    assert compiled.genesis == ()
    assert all(item.time >= LIVE_DAY_OFFSET for item in compiled.scheduled)
    assert compiled.end_time == LIVE_DAY_OFFSET + 17 * 3600 + 1800

    assert all(item.draft.payload.kind != "sim.wake" for item in compiled.scheduled), (
        "wake cohorts are minted at runtime by the day chain"
    )
    starts = [
        item
        for item in compiled.scheduled
        if item.draft.payload.kind == "sim.day.started"
    ]
    assert len(starts) == 1 and starts[0].time == LIVE_DAY_OFFSET
    assert len(compiled.personas) == 17, "every persona rides the day chain"

    emails = [
        item.draft.payload
        for item in compiled.scheduled
        if item.draft.payload.kind == "email.message"
    ]
    assert len(emails) == 4
    history_message_ids = {
        event.payload.message_id for event in history if event.tag == "email.message"
    }
    assert not history_message_ids & {email.message_id for email in emails}


def test_cast_matches_the_chronicle_roster() -> None:
    chronicle_ids = {person.person_id for person in EMPLOYEES} | {ARRIVAL.person_id}
    spec_personas = {
        person.person_id
        for person in LIVE_DAY_SPEC.people
        if person.persona is not None
    }
    assert spec_personas == chronicle_ids, (
        "every chronicle employee acts on the live day, nobody extra"
    )
    extras = [
        person.persona.extra_verbs
        for person in LIVE_DAY_SPEC.people
        if person.persona is not None and person.persona.extra_verbs
    ]
    assert len(extras) >= 6, "the extended vocabulary is genuinely exercised"
