"""The directed arcs: deterministic, coherent when ridden on top of the
procedural fabric, and correctly staged around the arrival."""

from datetime import date
from pathlib import Path

from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.chronicle.builder import Chronicle, TimedDraft
from workbench.simulation.chronicle.procedural import procedural_day
from workbench.workplaces.calder import (
    ARRIVAL,
    ARRIVAL_DATE,
    VOICE,
    WINDOW,
    build_genesis,
    day_profile,
    procedural_cast,
)
from workbench.workplaces.calder.arcs import (
    PBC_LIST_TITLE,
    WELCOME_SUBJECT,
    CalderDirector,
)

SEED = Seed(root=7)


def _walk(days: int) -> list[TimedDraft]:
    genesis = build_genesis(SEED)
    director = CalderDirector(genesis, SEED, genesis.minter)
    drafts: list[TimedDraft] = []
    for day_index in range(days):
        drafts.extend(director.drafts_for(WINDOW.iso_date(day_index), genesis.minter))
    return drafts


def test_arcs_are_deterministic() -> None:
    assert _walk(75) == _walk(75)


def test_arrival_day_contents() -> None:
    genesis = build_genesis(SEED)
    director = CalderDirector(genesis, SEED, genesis.minter)
    for day_index in range(WINDOW.day_count):
        day = WINDOW.iso_date(day_index)
        drafts = director.drafts_for(day, genesis.minter)
        if day != ARRIVAL_DATE:
            assert not any(draft.payload.kind == "person.record" for draft in drafts), (
                f"person.record outside the arrival day ({day})"
            )
            continue
        kinds = [draft.payload.kind for draft in drafts]
        assert kinds.count("person.record") == 1
        assert kinds.count("chat.conversation.created") == 1
        record = next(d for d in drafts if d.payload.kind == "person.record")
        assert record.payload.person_id == ARRIVAL.person_id
        welcome = [
            d for d in drafts if getattr(d.payload, "subject", "") == WELCOME_SUBJECT
        ]
        assert len(welcome) == 1
        clocks = [int(d.at) for d in drafts]
        assert clocks == sorted(clocks)
        break


def test_season_overtime_stays_in_season() -> None:
    genesis = build_genesis(SEED)
    director = CalderDirector(genesis, SEED, genesis.minter)
    season = (date(2026, 3, 1), date(2026, 4, 15))
    for day_index in range(WINDOW.day_count):
        day = WINDOW.iso_date(day_index)
        drafts = director.drafts_for(day, genesis.minter)
        overtime = [
            draft for draft in drafts if draft.payload.kind == "work.time.logged"
        ]
        current = date.fromisoformat(day)
        if not season[0] <= current <= season[1]:
            assert not overtime, f"directed time entry outside season on {day}"
        for draft in overtime:
            if draft.payload.person_id == ARRIVAL.person_id:
                assert day > ARRIVAL_DATE, "Maya logged time before arriving"


def test_chronicle_with_arcs_validates(tmp_path: Path) -> None:
    """Seventy days — through the arrival and into filing season — built
    with procedural traffic plus arcs must cohere event by event."""

    genesis = build_genesis(SEED)
    minter = genesis.minter
    director = CalderDirector(genesis, SEED, minter)
    before = procedural_cast(genesis)
    after = procedural_cast(genesis, arrival_dm_id=director.arrival_dm_id)

    log_path = tmp_path / "world.jsonl"
    chronicle = Chronicle(log_path, window=WINDOW)
    chronicle.write_genesis(genesis.events)
    for day_index in range(70):
        day = WINDOW.iso_date(day_index)
        cast = after if day > ARRIVAL_DATE else before
        drafts = list(
            procedural_day(
                seed=SEED,
                window=WINDOW,
                day_index=day_index,
                cast=cast,
                voice=VOICE,
                minter=minter,
                profile=day_profile(SEED, day_index),
            )
        )
        drafts.extend(director.drafts_for(day, minter))
        drafts.sort(key=lambda draft: int(draft.at))
        chronicle.add_procedural_day(day_index, drafts)
    events = chronicle.finish()

    report = validate_events(events)
    assert report.ok, report.findings[:8]

    tags = [event.tag for event in read_events(log_path)]
    assert tags.count("person.record") == 16 + 13 + 1, "Maya's record landed"
    titles = [
        event.payload.title for event in events if event.tag == "document.created"
    ]
    assert PBC_LIST_TITLE in titles
    assert any(title.startswith("Reporting Package") for title in titles)
    assert any(
        event.tag == "email.message" and event.payload.attachments for event in events
    ), "close packages ride as attachments"
