"""Bounded prompt views for long histories: the pending list caps at the
youngest PENDING_CAP items and conversation rendering keeps only the
recent tail — while below each cap the views are byte-identical to the
unbounded forms, which is what keeps recorded cassettes valid."""

from core.actions import IntentActionSpec
from core.events import Event
from core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from core.events.email import EmailMessagePayload
from core.events.people import PersonRecordPayload
from simulation.persona.rendering import (
    CONVERSATION_TAIL,
    render_conversation,
)
from simulation.persona.working_memory import (
    PENDING_CAP,
    WorkingMemoryComponent,
)

ME = "per-recipient"


def _email(index: int) -> Event:
    payload = EmailMessagePayload(
        kind="email.message",
        message_id=f"msg-{index:06d}",
        thread_id=f"thr-{index:06d}",
        in_reply_to=None,
        sender="per-sender",
        to=(ME,),
        subject=f"Request {index}",
        body="Please take a look.",
    )
    return Event(
        seq=index, time=index * 600, tag=payload.kind, source="x", payload=payload
    )


async def _memory(count: int) -> WorkingMemoryComponent:
    memory = WorkingMemoryComponent(person_id=ME)
    for index in range(count):
        await memory.pre_observe(_email(index))
    return memory


async def test_below_cap_is_the_unbounded_view() -> None:
    memory = await _memory(5)
    items = memory.pending_items()
    assert items == memory._pending_all()
    assert [item.ref for item in items] == [f"msg-{i:06d}" for i in range(5)]


async def test_above_cap_keeps_youngest_in_stable_order() -> None:
    total = PENDING_CAP + 7
    memory = await _memory(total)
    items = memory.pending_items()
    assert len(items) == PENDING_CAP
    expected = [f"msg-{i:06d}" for i in range(total - PENDING_CAP, total)]
    assert [item.ref for item in items] == expected


async def test_situation_line_marks_truncation() -> None:
    spec = IntentActionSpec(call_to_action="Decide your next action.")
    small = await _memory(3)
    block = await small.pre_act(spec)
    assert "You have 3 pending item(s)." in block.content

    big = await _memory(PENDING_CAP + 12)
    block = await big.pre_act(spec)
    assert f"You have {PENDING_CAP}+ pending item(s)" in block.content


def _conversation_events(message_count: int) -> list[Event]:
    person = PersonRecordPayload(
        kind="person.record",
        person_id="per-sender",
        name="Sam Sender",
        email_address="sam@example.test",
        title="Sender",
        department="Ops",
        manager=None,
        affiliation="internal",
        timezone="UTC",
    )
    created = ChatConversationCreatedPayload(
        kind="chat.conversation.created",
        conversation_id="cnv-000001",
        conversation_type="channel",
        name="#room",
        members=("per-sender", ME),
    )
    events = [
        Event(seq=0, time=0, tag=person.kind, source="gm", payload=person),
        Event(seq=1, time=0, tag=created.kind, source="gm", payload=created),
    ]
    for index in range(message_count):
        payload = ChatMessagePayload(
            kind="chat.message",
            chat_message_id=f"chm-{index:06d}",
            conversation_id="cnv-000001",
            reply_to=None,
            sender="per-sender",
            body=f"message number {index}",
        )
        events.append(
            Event(
                seq=index + 2,
                time=(index + 1) * 60,
                tag=payload.kind,
                source="x",
                payload=payload,
            )
        )
    return events


def test_conversation_rendering_keeps_recent_tail() -> None:
    short = _conversation_events(CONVERSATION_TAIL)
    rendered_short = render_conversation(short, "cnv-000001")
    assert "message number 0" in rendered_short

    long = _conversation_events(CONVERSATION_TAIL + 15)
    rendered = render_conversation(long, "cnv-000001")
    assert "message number 0" not in rendered
    assert f"message number {CONVERSATION_TAIL + 14}" in rendered
    assert rendered.count("\n") == CONVERSATION_TAIL - 1
