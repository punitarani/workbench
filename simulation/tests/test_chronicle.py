"""Chronicle contract tests: calendar math, minter recovery, the day-segment
builder, and procedural-generator determinism."""

import itertools
from pathlib import Path

import pytest

from workbench.core.errors import WorldLogIntegrityError
from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.control import SimRunStartedPayload
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.events.tickets import TicketCreatedPayload
from workbench.core.seed import Seed
from workbench.core.worldlog import read_events, validate_events
from workbench.simulation.chronicle.builder import Chronicle, TimedDraft
from workbench.simulation.chronicle.calendar import SECONDS_PER_DAY, CalendarWindow
from workbench.simulation.chronicle.minter import minter_from_events
from workbench.simulation.chronicle.procedural import (
    CastMember,
    OpenMatter,
    ProceduralCast,
    procedural_day,
)
from workbench.simulation.errors import ChronicleError

PHASE2_WINDOW = CalendarWindow(
    start_date="2026-03-02", end_date="2026-06-30", timezone="America/Los_Angeles"
)


def _person(person_id: str, name: str, affiliation: str) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{name.split()[0].lower()}@chronicle.example",
        title="Counsel",
        department="Legal",
        manager=None,
        affiliation=affiliation,
        timezone="America/Los_Angeles",
    )


def small_genesis() -> list[Event]:
    payloads = [
        SimRunStartedPayload(
            kind="sim.run.started",
            run_id="run-chronicle-test",
            seed_root=7,
            workplace_id="chronicle-test",
            config_hash="0" * 64,
            schema_version=1,
            epoch="2026-03-02T00:00:00-08:00",
            timezone="America/Los_Angeles",
        ),
        _person("per-ann-liu", "Ann Liu", "internal"),
        _person("per-bob-tran", "Bob Tran", "internal"),
        _person("per-eve-moss", "Eve Moss", "external"),
        ChatConversationCreatedPayload(
            kind="chat.conversation.created",
            conversation_id="cnv-000001",
            conversation_type="channel",
            name="#general",
            members=("per-ann-liu", "per-bob-tran"),
            topic="Daily chatter",
            purpose="Everything.",
        ),
        TicketCreatedPayload(
            kind="ticket.created",
            ticket_id="tkt-000001",
            actor="per-ann-liu",
            title="Test matter",
            description="A matter to log time against.",
            requester="per-bob-tran",
            assignee="per-ann-liu",
            status="open",
            priority="normal",
            ticket_type="general",
        ),
    ]
    return [
        Event(seq=seq, time=0, tag=payload.kind, source="gm", payload=payload)
        for seq, payload in enumerate(payloads)
    ]


def small_cast() -> ProceduralCast:
    ann = CastMember(person_id="per-ann-liu", name="Ann Liu")
    bob = CastMember(person_id="per-bob-tran", name="Bob Tran")
    eve = CastMember(person_id="per-eve-moss", name="Eve Moss")
    return ProceduralCast(
        internal=(ann, bob),
        timekeepers=(ann,),
        externals=(eve,),
        standup_channel="cnv-000001",
        matters=(
            OpenMatter(
                ticket_id="tkt-000001", label="Test matter", assignee="per-ann-liu"
            ),
        ),
    )


_CHAT_IDS = itertools.count(1)


def _chat_draft(at: int, body: str = "hello") -> TimedDraft:
    return TimedDraft(
        at=at,
        source="ann-liu",
        payload=ChatMessagePayload(
            kind="chat.message",
            chat_message_id=f"chm-{next(_CHAT_IDS):06d}",
            conversation_id="cnv-000001",
            reply_to=None,
            sender="per-ann-liu",
            body=body,
        ),
    )


class TestCalendarWindow:
    def test_matches_the_phase2_plan(self) -> None:
        assert PHASE2_WINDOW.day_count == 121
        workdays = PHASE2_WINDOW.workdays()
        assert len(workdays) == 87
        assert workdays[0] == 0
        assert PHASE2_WINDOW.iso_date(0) == "2026-03-02"
        assert PHASE2_WINDOW.iso_date(120) == "2026-06-30"

    def test_workday_math_skips_weekends(self) -> None:
        assert all(PHASE2_WINDOW.is_workday(index) for index in range(5))
        assert not PHASE2_WINDOW.is_workday(5), "2026-03-07 is a Saturday"
        assert not PHASE2_WINDOW.is_workday(6), "2026-03-08 is a Sunday"
        assert PHASE2_WINDOW.is_workday(7)
        assert 5 not in PHASE2_WINDOW.workdays()

    def test_day_offset_is_a_flat_day_count(self) -> None:
        assert PHASE2_WINDOW.day_offset(0) == 0
        assert PHASE2_WINDOW.day_offset(3) == 3 * SECONDS_PER_DAY

    def test_epoch_renders_from_explicit_strings(self) -> None:
        assert PHASE2_WINDOW.epoch().isoformat() == "2026-03-02T00:00:00-08:00"

    def test_out_of_window_day_index_raises(self) -> None:
        with pytest.raises(ChronicleError):
            PHASE2_WINDOW.iso_date(121)
        with pytest.raises(ChronicleError):
            PHASE2_WINDOW.day_offset(-1)

    def test_inverted_window_rejected(self) -> None:
        with pytest.raises(ValueError):
            CalendarWindow(
                start_date="2026-06-30", end_date="2026-03-02", timezone="UTC"
            )


class TestMinterFromEvents:
    def test_counters_continue_after_the_max_per_prefix(self) -> None:
        events = small_genesis()
        email = EmailMessagePayload(
            kind="email.message",
            message_id="msg-000003",
            thread_id="thr-000002",
            in_reply_to=None,
            sender="per-eve-moss",
            to=("per-ann-liu",),
            subject="Existing traffic",
            body="Mentioning tkt-999999 in prose must not bump any counter.",
        )
        events.append(
            Event(
                seq=len(events),
                time=100,
                tag=email.kind,
                source="eve-moss",
                payload=email,
            )
        )
        minter = minter_from_events(events)
        assert minter.mint("msg") == "msg-000004"
        assert minter.mint("thr") == "thr-000003"
        assert minter.mint("cnv") == "cnv-000002"
        assert minter.mint("tkt") == "tkt-000002", "prose mentions do not count"
        assert minter.mint("cal") == "cal-000001", "unseen prefixes start fresh"

    def test_slug_ids_without_counters_are_ignored(self) -> None:
        minter = minter_from_events(small_genesis())
        assert "per" not in minter.counters


class TestChronicleBuilder:
    def test_day_markers_seq_and_absolute_time(self, tmp_path: Path) -> None:
        log = tmp_path / "world.jsonl"
        chronicle = Chronicle(log, window=PHASE2_WINDOW)
        genesis = small_genesis()
        chronicle.write_genesis(genesis)
        chronicle.add_procedural_day(
            0, [_chat_draft(9 * 3600, "day one"), _chat_draft(10 * 3600, "later")]
        )
        chronicle.add_procedural_day(1, [_chat_draft(9 * 3600, "day two")])
        events = chronicle.finish()

        assert [event.seq for event in events] == list(range(len(events)))
        tail = events[len(genesis) :]
        assert [event.tag for event in tail] == [
            "sim.day.started",
            "chat.message",
            "chat.message",
            "sim.day.ended",
            "sim.day.started",
            "chat.message",
            "sim.day.ended",
        ]
        day_one_started, first, second, day_one_ended = tail[:4]
        assert day_one_started.payload.day == "2026-03-02"
        assert int(day_one_started.time) == 0
        assert int(first.time) == 9 * 3600
        assert int(second.time) == 10 * 3600
        assert int(day_one_ended.time) == SECONDS_PER_DAY - 1
        day_two_started, third, day_two_ended = tail[4:]
        assert day_two_started.payload.day == "2026-03-03"
        assert int(day_two_started.time) == SECONDS_PER_DAY
        assert int(third.time) == SECONDS_PER_DAY + 9 * 3600
        assert int(day_two_ended.time) == 2 * SECONDS_PER_DAY - 1
        assert list(events) == read_events(log)

    def test_segments_append_to_one_growing_log(self, tmp_path: Path) -> None:
        log = tmp_path / "world.jsonl"
        chronicle = Chronicle(log, window=PHASE2_WINDOW)
        chronicle.write_genesis(small_genesis())
        after_genesis = log.read_bytes()
        chronicle.add_procedural_day(0, [_chat_draft(9 * 3600)])
        after_day = log.read_bytes()
        assert after_day.startswith(after_genesis)
        assert len(after_day) > len(after_genesis)

    def test_days_must_ascend(self, tmp_path: Path) -> None:
        chronicle = Chronicle(tmp_path / "world.jsonl", window=PHASE2_WINDOW)
        chronicle.write_genesis(small_genesis())
        chronicle.add_procedural_day(1, [_chat_draft(9 * 3600)])
        with pytest.raises(ChronicleError):
            chronicle.add_procedural_day(1, [])
        with pytest.raises(ChronicleError):
            chronicle.add_procedural_day(0, [])

    def test_regressing_drafts_rejected_before_writing(self, tmp_path: Path) -> None:
        log = tmp_path / "world.jsonl"
        chronicle = Chronicle(log, window=PHASE2_WINDOW)
        chronicle.write_genesis(small_genesis())
        before = log.read_bytes()
        with pytest.raises(ChronicleError):
            chronicle.add_procedural_day(
                0, [_chat_draft(10 * 3600), _chat_draft(9 * 3600)]
            )
        assert log.read_bytes() == before, "a rejected day writes nothing"

    def test_days_require_genesis_first(self, tmp_path: Path) -> None:
        chronicle = Chronicle(tmp_path / "world.jsonl", window=PHASE2_WINDOW)
        with pytest.raises(ChronicleError):
            chronicle.add_procedural_day(0, [])

    def test_finish_raises_on_incoherent_log(self, tmp_path: Path) -> None:
        chronicle = Chronicle(tmp_path / "world.jsonl", window=PHASE2_WINDOW)
        chronicle.write_genesis(small_genesis())
        ghost = TimedDraft(
            at=9 * 3600,
            source="ghost",
            payload=ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000099",
                conversation_id="cnv-000001",
                reply_to=None,
                sender="per-ghost",
                body="boo",
            ),
        )
        chronicle.add_procedural_day(0, [ghost])
        with pytest.raises(WorldLogIntegrityError):
            chronicle.finish()


class TestProceduralDays:
    def test_same_seed_same_bytes(self) -> None:
        first = procedural_day(
            seed=Seed(root=42),
            window=PHASE2_WINDOW,
            day_index=0,
            cast=small_cast(),
            minter=minter_from_events(small_genesis()),
        )
        second = procedural_day(
            seed=Seed(root=42),
            window=PHASE2_WINDOW,
            day_index=0,
            cast=small_cast(),
            minter=minter_from_events(small_genesis()),
        )
        assert [draft.model_dump_json() for draft in first] == [
            draft.model_dump_json() for draft in second
        ]

    def test_different_seed_or_day_changes_the_traffic(self) -> None:
        base = procedural_day(
            seed=Seed(root=42),
            window=PHASE2_WINDOW,
            day_index=0,
            cast=small_cast(),
            minter=minter_from_events(small_genesis()),
        )
        other_seed = procedural_day(
            seed=Seed(root=43),
            window=PHASE2_WINDOW,
            day_index=0,
            cast=small_cast(),
            minter=minter_from_events(small_genesis()),
        )
        other_day = procedural_day(
            seed=Seed(root=42),
            window=PHASE2_WINDOW,
            day_index=1,
            cast=small_cast(),
            minter=minter_from_events(small_genesis()),
        )
        dumps = [draft.model_dump_json() for draft in base]
        assert dumps != [draft.model_dump_json() for draft in other_seed]
        assert dumps != [draft.model_dump_json() for draft in other_day]

    def test_refs_resolve_across_a_procedural_week(self, tmp_path: Path) -> None:
        log = tmp_path / "world.jsonl"
        chronicle = Chronicle(log, window=PHASE2_WINDOW)
        genesis = small_genesis()
        chronicle.write_genesis(genesis)
        minter = minter_from_events(genesis)
        cast = small_cast()
        for day_index in PHASE2_WINDOW.workdays()[:5]:
            drafts = procedural_day(
                seed=Seed(root=42),
                window=PHASE2_WINDOW,
                day_index=day_index,
                cast=cast,
                minter=minter,
            )
            chronicle.add_procedural_day(day_index, drafts)
        events = chronicle.finish()
        report = validate_events(list(events))
        assert report.findings == ()
        tags = {event.tag for event in events}
        assert {
            "chat.message",
            "email.message",
            "work.time.logged",
            "ticket.commented",
        } <= tags
        started = [event for event in events if event.tag == "sim.day.started"]
        ended = [event for event in events if event.tag == "sim.day.ended"]
        assert len(started) == 5 and len(ended) == 5
