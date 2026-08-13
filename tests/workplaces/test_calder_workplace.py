"""Structural gates for the Calder & Finch workplace: genesis coheres,
the cast grows correctly at the arrival, and the channel-silent member
never posts where the world model says she cannot.
"""

from datetime import date
from pathlib import Path

from workbench.core.artifacts import parse_formatted, parse_spreadsheet
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.documents import DocumentCreatedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.work import TimeLoggedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.chronicle.builder import Chronicle
from workbench.simulation.chronicle.procedural import procedural_day
from workbench.workplaces.calder import (
    ARRIVAL,
    VOICE,
    WINDOW,
    build_genesis,
    day_profile,
    procedural_cast,
)

SEED = Seed(root=7)


def test_genesis_validates_and_counts() -> None:
    genesis = build_genesis(SEED)
    report = validate_events(genesis.events)
    assert report.ok, report.findings
    tags = [event.tag for event in genesis.events]
    assert tags[0] == "sim.run.started"
    assert tags.count("person.record") == 16 + 13
    assert tags.count("org.record") == 13
    assert tags.count("chat.conversation.created") == 4 + 14
    assert tags.count("document.created") == 8
    assert tags.count("ticket.created") == 12
    assert len(genesis.events) == 81
    assert ARRIVAL.person_id not in {
        payload.person_id
        for payload in (event.payload for event in genesis.events)
        if payload.kind == "person.record"
    }


def test_structured_seed_documents_parse() -> None:
    genesis = build_genesis(SEED)
    formats = {
        event.payload.title: event.payload
        for event in genesis.events
        if isinstance(event.payload, DocumentCreatedPayload)
    }
    rates = formats["Standard Rate Sheet 2026"]
    assert rates.content_format == "spreadsheet"
    sheet = parse_spreadsheet(rates.content).sheets[0]
    assert sheet.columns[0] == "Timekeeper"
    assert len(sheet.rows) == 13, "the rate sheet predates Maya"

    clients = parse_spreadsheet(formats["Client Master List"].content).sheets[0]
    assert len(clients.rows) == 10

    checklist = formats["Monthly Close Checklist"]
    assert checklist.content_format == "formatted"
    blocks = parse_formatted(checklist.content).blocks
    assert blocks[0].kind == "heading"


def test_cast_grows_at_arrival() -> None:
    genesis = build_genesis(SEED)
    before = procedural_cast(genesis)
    assert len(before.timekeepers) == 13
    assert before.channel_silent == ()
    assert all(ARRIVAL.person_id not in matter.staff for matter in before.matters)

    after = procedural_cast(genesis, arrival_dm_id="cnv-999999")
    assert len(after.timekeepers) == 14
    assert [member.person_id for member in after.channel_silent] == [ARRIVAL.person_id]
    assert after.dms[-1].conversation_id == "cnv-999999"
    staffed = [
        matter.label for matter in after.matters if ARRIVAL.person_id in matter.staff
    ]
    assert len(staffed) == 3


def test_channel_silent_member_posts_no_channel_messages(tmp_path: Path) -> None:
    """Ten procedural days with Maya active: she emails and logs time,
    but never speaks in a conversation she is not a member of."""

    genesis = build_genesis(SEED)
    cast = procedural_cast(genesis, arrival_dm_id="cnv-999999")
    minter = genesis.minter

    maya = ARRIVAL.person_id
    channel_ids = {
        event.payload.conversation_id
        for event in genesis.events
        if isinstance(event.payload, ChatConversationCreatedPayload)
        and event.payload.conversation_type == "channel"
    }

    chat_senders: set[tuple[str, str]] = set()
    emailed = False
    logged = False
    for day_index in range(10):
        if not WINDOW.is_workday(day_index):
            continue
        drafts = procedural_day(
            seed=SEED,
            window=WINDOW,
            day_index=day_index,
            cast=cast,
            voice=VOICE,
            minter=minter,
            profile=day_profile(SEED, day_index),
        )
        for draft in drafts:
            payload = draft.payload
            if isinstance(payload, ChatMessagePayload):
                chat_senders.add((payload.sender, payload.conversation_id))
            elif isinstance(payload, EmailMessagePayload):
                if maya == payload.sender or maya in payload.to:
                    emailed = True
            elif isinstance(payload, TimeLoggedPayload):
                if payload.person_id == maya:
                    logged = True

    assert not any(
        sender == maya and conversation in channel_ids
        for sender, conversation in chat_senders
    ), "a channel-silent member posted to a genesis channel"
    assert emailed, "Maya participates in the email fabric"
    assert logged, "Maya logs time as a timekeeper"


def test_three_day_chronicle_is_deterministic(tmp_path: Path) -> None:
    def build(path: Path) -> bytes:
        genesis = build_genesis(SEED)
        chronicle = Chronicle(path, window=WINDOW)
        chronicle.write_genesis(genesis.events)
        cast = procedural_cast(genesis)
        for day_index in range(3):
            drafts = procedural_day(
                seed=SEED,
                window=WINDOW,
                day_index=day_index,
                cast=cast,
                voice=VOICE,
                minter=genesis.minter,
                profile=day_profile(SEED, day_index),
            )
            chronicle.add_procedural_day(day_index, list(drafts))
        chronicle.finish()
        return path.read_bytes()

    first = build(tmp_path / "one.jsonl")
    second = build(tmp_path / "two.jsonl")
    assert first == second
    events = read_events(tmp_path / "one.jsonl")
    assert validate_events(events).ok
    assert len(events) > 200, "three workdays carry real traffic"


def test_day_profile_shapes() -> None:
    profiles = {
        WINDOW.iso_date(index): day_profile(SEED, index)
        for index in range(WINDOW.day_count)
    }
    assert profiles["2026-01-19"].kind == "holiday"
    assert profiles["2026-07-03"].intensity < 0.2
    assert profiles["2026-01-06"].kind == "workday"
    saturdays_in_season = [
        profile
        for day, profile in profiles.items()
        if "2026-02-01" <= day <= "2026-04-15"
        and profile.kind == "weekend"
        and date.fromisoformat(day).weekday() == 5
    ]
    off_season = [
        profile
        for day, profile in profiles.items()
        if day > "2026-05-01"
        and profile.kind == "weekend"
        and date.fromisoformat(day).weekday() == 5
    ]
    season_mean = sum(p.intensity for p in saturdays_in_season) / len(
        saturdays_in_season
    )
    off_mean = sum(p.intensity for p in off_season) / len(off_season)
    assert season_mean > 2 * off_mean, "filing-season Saturdays run hot"
