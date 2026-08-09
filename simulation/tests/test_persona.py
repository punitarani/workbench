from persona_fixtures import DANIEL, observed_events

from workbench.core.actions import IntentAction, IntentActionSpec
from workbench.core.intents import EmailDraft, EmailIntent
from workbench.core.worldlog.views import inbox
from workbench.simulation.persona.rendering import render_identity, render_thread
from workbench.simulation.persona.working_memory import WorkingMemoryComponent


def spec() -> IntentActionSpec:
    return IntentActionSpec(call_to_action="Decide your next action.")


def test_identity_block_is_byte_stable_and_complete() -> None:
    first = render_identity(DANIEL)
    second = render_identity(DANIEL)
    assert first == second
    for fragment in ("Daniel Reyes", "Senior Counsel", "lowercase", "flagging"):
        assert fragment in first


async def make_memory() -> WorkingMemoryComponent:
    memory = WorkingMemoryComponent(person_id="per-daniel-reyes")
    for event in observed_events():
        await memory.pre_observe(event)
    return memory


async def test_working_memory_matches_core_views() -> None:
    memory = await make_memory()
    from_view = inbox(observed_events(), "per-daniel-reyes")
    from_memory = inbox(memory.events(), "per-daniel-reyes")
    assert from_memory == from_view
    assert len(from_memory) == 1


async def test_pending_items_cover_unanswered_email_and_chat() -> None:
    memory = await make_memory()
    pending = memory.pending_items()
    refs = {item.ref for item in pending}
    assert "msg-000001" in refs
    assert any(item.channel == "chat" for item in pending)


async def test_thread_rendering_names_people() -> None:
    memory = await make_memory()
    rendered = render_thread(memory.events(), "thr-000001")
    assert "Jess Alvarez" in rendered
    assert "Vendor NDA - need your eyes" in rendered
    assert "review the attached NDA" in rendered


async def test_established_facts_grow_on_sent_intents() -> None:
    memory = await make_memory()
    intent = EmailIntent(
        thread_ref="thr-000001",
        reply_to_ref="msg-000001",
        draft=EmailDraft(
            to=("Jess Alvarez",),
            subject="Re: Vendor NDA - need your eyes",
            body="On it; expect redlines by Thursday.",
            summary="Told Jess redlines arrive by Thursday.",
        ),
    )
    await memory.post_act(IntentAction(intent=intent))
    assert "Told Jess redlines arrive by Thursday." in memory.get_state().facts


async def test_state_round_trips() -> None:
    memory = await make_memory()
    state = memory.get_state()
    fresh = WorkingMemoryComponent(person_id="per-daniel-reyes")
    fresh.set_state(state)
    assert fresh.pending_items() == memory.pending_items()


async def test_situation_block_lists_documents_and_pending() -> None:
    from workbench.core.events import Event
    from workbench.core.events.documents import DocumentCreatedPayload

    memory = await make_memory()
    doc = DocumentCreatedPayload(
        kind="document.created",
        document_id="doc-000009",
        author="per-daniel-reyes",
        title="NDA Playbook",
        path="/legal/playbooks/nda-playbook.md",
        location="repository",
        content_format="markdown",
        content="x",
    )
    await memory.pre_observe(
        Event(seq=90, time=40000, tag=doc.kind, source="gm", payload=doc)
    )
    block = await memory.pre_act(spec())
    assert block is not None
    assert "/legal/playbooks/nda-playbook.md" in block.content
    assert "pending" in block.content.casefold()


async def test_facts_record_ticket_and_document_actions() -> None:
    from workbench.core.intents import (
        DocumentEdit,
        DocumentEditIntent,
        TicketCreateSpec,
        TicketIntent,
    )

    memory = await make_memory()
    await memory.post_act(
        IntentAction(
            intent=TicketIntent(
                ticket_ref=None,
                create=TicketCreateSpec(
                    title="Review Vantage NDA",
                    description="d",
                    requester_ref="Jess Alvarez",
                    assignee_ref=None,
                    status="open",
                    priority="normal",
                    ticket_type="nda-review",
                ),
            )
        )
    )
    await memory.post_act(
        IntentAction(
            intent=DocumentEditIntent(
                document_ref="doc-000001",
                edit=DocumentEdit(
                    new_content="x", change_summary="Applied the term cap."
                ),
            )
        )
    )
    facts = memory.get_state().facts
    assert any("Review Vantage NDA" in f for f in facts)
    assert any("Applied the term cap" in f for f in facts)


async def test_observed_own_reply_clears_pending() -> None:
    from workbench.core.events import Event
    from workbench.core.events.email import EmailMessagePayload

    memory = await make_memory()
    assert any(i.ref == "msg-000001" for i in memory.pending_items())
    own_reply = EmailMessagePayload(
        kind="email.message",
        message_id="msg-000900",
        thread_id="thr-000001",
        in_reply_to="msg-000001",
        sender="per-daniel-reyes",
        to=("per-jess-alvarez",),
        cc=(),
        subject="Re: Vendor NDA - need your eyes",
        body="On it.",
        attachments=(),
    )
    await memory.pre_observe(
        Event(seq=91, time=41_000, tag=own_reply.kind, source="x", payload=own_reply)
    )
    assert not any(i.ref == "msg-000001" for i in memory.pending_items()), (
        "an observed own reply must clear the pending item"
    )


async def test_situation_block_lists_chat_channels_for_initiating() -> None:
    """A silent channel must still be visible: the persona needs its name to
    post an update without waiting to be spoken to (GM resolves names)."""
    from workbench.core.events import Event
    from workbench.core.events.chat import ChatConversationCreatedPayload

    memory = await make_memory()
    other = ChatConversationCreatedPayload(
        kind="chat.conversation.created",
        conversation_id="cnv-000009",
        conversation_type="channel",
        name="#partners-only",
        members=("per-jess-alvarez",),
    )
    await memory.pre_observe(
        Event(seq=91, time=40001, tag=other.kind, source="gm", payload=other)
    )
    block = await memory.pre_act(spec())
    assert block is not None
    assert "#legal" in block.content, "member channels render by name"
    assert "#partners-only" not in block.content, "non-member channels do not"
