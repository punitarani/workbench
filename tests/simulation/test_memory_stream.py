"""C1: the memory stream folds observed events into scored records, the
GM grounds cognition intents into world events, and rejections route back
to the entity that earned them."""

from test_grounded_gm import last_event, make_gm, spec
from worldlog_fixtures import coherent_events

from core.actions import IntentAction
from core.events import Event
from core.events.agent import MemoryBullet, PlanBlock
from core.events.chat import ChatMessagePayload
from core.events.control import SimGmNotePayload
from core.events.email import EmailMessagePayload
from core.intents import (
    AgentNoteIntent,
    AgentPlanIntent,
    EmailDraft,
    EmailIntent,
)
from simulation.persona.memory_stream import MemoryStreamComponent

ME = "per-daniel-reyes"
MY_ENTITY = "daniel"


def _email(seq: int, *, to: tuple[str, ...], cc: tuple[str, ...] = ()) -> Event:
    payload = EmailMessagePayload(
        kind="email.message",
        message_id=f"msg-{seq:06d}",
        thread_id=f"thr-{seq:06d}",
        in_reply_to=None,
        sender="per-jess-alvarez",
        to=to,
        cc=cc,
        subject=f"Request {seq}",
        body="Please review the attached.",
    )
    return Event(
        seq=seq, time=seq * 60, tag=payload.kind, source="jess", payload=payload
    )


async def _stream(events: list[Event]) -> MemoryStreamComponent:
    stream = MemoryStreamComponent(person_id=ME, entity_name=MY_ENTITY)
    for event in events:
        await stream.pre_observe(event)
    return stream


async def test_fold_importance_rules() -> None:
    note = SimGmNotePayload(
        kind="sim.gm.note",
        note="Rejected action from daniel: unknown thread",
        entity=MY_ENTITY,
    )
    other_note = SimGmNotePayload(
        kind="sim.gm.note", note="Rejected action from tom: x", entity="tom"
    )
    chat = ChatMessagePayload(
        kind="chat.message",
        chat_message_id="chm-000001",
        conversation_id="cnv-000001",
        reply_to=None,
        sender="per-jess-alvarez",
        body="daniel-reyes can you look at the redline?",
    )
    events = [
        _email(1, to=(ME,)),
        _email(2, to=("per-tom-okafor",), cc=(ME,)),
        Event(seq=3, time=200, tag=chat.kind, source="jess", payload=chat),
        Event(seq=4, time=300, tag=note.kind, source="gm", payload=note),
        Event(seq=5, time=400, tag=other_note.kind, source="gm", payload=other_note),
    ]
    stream = await _stream(events)
    records = stream.records()
    assert [record.importance for record in records] == [7, 4, 7, 10]
    assert records[3].kind == "rejection"
    assert "msg-000001" in records[0].refs


async def test_agent_memory_event_folds_per_bullet() -> None:
    from core.events.agent import SimAgentMemoryPayload

    payload = SimAgentMemoryPayload(
        kind="sim.agent.memory",
        note_id="mem-000001",
        entity=MY_ENTITY,
        note_kind="daily_summary",
        day="2026-03-12",
        bullets=(
            MemoryBullet(
                text="Vantage NDA needs the term cap",
                importance=8,
                refs=("thr-000001",),
            ),
            MemoryBullet(text="Quiet afternoon", importance=2),
        ),
    )
    event = Event(
        seq=9, time=60_000, tag=payload.kind, source=MY_ENTITY, payload=payload
    )
    stream = await _stream([_email(1, to=(ME,)), event])
    records = stream.records()
    assert len(records) == 3
    summaries = [record for record in records if record.kind == "summary"]
    assert [record.importance for record in summaries] == [8, 2]
    touching = stream.records_touching(frozenset({"thr-000001"}))
    assert any(record.kind == "summary" for record in touching)


async def test_snapshot_round_trip_rehydrates() -> None:
    events = [_email(1, to=(ME,)), _email(2, to=(ME,))]
    stream = await _stream(events)
    state = stream.get_state()
    fresh = MemoryStreamComponent(person_id=ME, entity_name=MY_ENTITY)
    fresh.set_state(state)
    fresh.rehydrate({str(event.event_id): event for event in events})
    assert fresh.records() == stream.records()


async def test_gm_grounds_agent_note_and_filters_refs() -> None:
    gm = make_gm()
    intent = AgentNoteIntent(
        day="2026-03-12",
        note_kind="daily_summary",
        bullets=(
            MemoryBullet(
                text="Followed up on the NDA",
                importance=7,
                refs=("thr-000001", "tkt-999999"),
            ),
        ),
        open_loops=("chase Jess",),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    (draft,) = decision.drafts
    payload = draft.payload
    assert payload.kind == "sim.agent.memory"
    assert payload.entity == "daniel"
    assert payload.note_id.startswith("mem-")
    known = "thr-000001" in {ref for bullet in payload.bullets for ref in bullet.refs}
    assert "tkt-999999" not in {
        ref for bullet in payload.bullets for ref in bullet.refs
    }, "unknown refs are dropped, not rejected"
    del known


async def test_gm_grounds_plan_with_clamping_and_revisions() -> None:
    gm = make_gm()
    intent = AgentPlanIntent(
        day="2026-03-12",
        blocks=(
            PlanBlock(start=9 * 3600, end=11 * 3600, focus="NDA redline"),
            PlanBlock(start=10 * 3600, end=12 * 3600, focus="Email catch-up"),
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    (draft,) = decision.drafts
    payload = draft.payload
    assert payload.kind == "sim.agent.plan"
    assert payload.revision == 1
    starts_ends = [(block.start, block.end) for block in payload.blocks]
    assert starts_ends == [(9 * 3600, 11 * 3600), (11 * 3600, 12 * 3600)], (
        "overlapping blocks are trimmed, not rejected"
    )

    # Once the first plan lands in the world, the next one is revision 2.
    event = draft.to_event(seq=999, time=70_000)
    await gm.route(event)
    second = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    assert second.drafts[0].payload.revision == 2


async def test_rejection_note_carries_entity_and_routes_back() -> None:
    gm = make_gm()
    bad = EmailIntent(
        thread_ref="thr-does-not-exist",
        reply_to_ref=None,
        draft=EmailDraft(
            to=("Jess Alvarez",),
            subject="x",
            body="y",
            summary="z",
        ),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=bad), spec(), last_event()
    )
    (draft,) = decision.drafts
    assert draft.payload.kind == "sim.gm.note"
    assert draft.payload.entity == "daniel"

    note_event = draft.to_event(seq=998, time=69_000)
    observers = await gm.route(note_event)
    assert observers == ("daniel",), "the rejected actor observes the note"


async def test_agent_events_route_only_to_their_entity() -> None:
    gm = make_gm()
    intent = AgentNoteIntent(
        day="2026-03-12",
        bullets=(MemoryBullet(text="note", importance=5),),
    )
    decision = await gm.resolve(
        "daniel", IntentAction(intent=intent), spec(), last_event()
    )
    event = decision.drafts[0].to_event(seq=997, time=68_000)
    assert await gm.route(event) == ("daniel",)
    assert gm.observers_for(event.payload) == ("daniel",)
    assert len(coherent_events()) > 0
