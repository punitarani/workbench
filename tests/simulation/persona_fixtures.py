"""Shared persona test fixtures: params and a small observed-event history."""

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.simulation.persona.params import (
    ChannelStyle,
    KnowledgeItem,
    ProfessionalWorkerParams,
    Relationship,
)

DANIEL = ProfessionalWorkerParams(
    person_id="per-daniel-reyes",
    name="Daniel Reyes",
    title="Senior Counsel, Commercial",
    seniority="senior",
    role_description="Owns commercial contracts; the go-to for NDA standards.",
    personality="Direct, dry humor, allergic to legalese in chat.",
    channel_style=ChannelStyle(
        email_register="Formal but warm; greets by first name; signs 'Best, Daniel'.",
        chat_register="Terse, lowercase, no sign-off.",
        quirks="Uses 'flagging' when raising a risk.",
    ),
    working_hours="09:00-17:30",
    manager="per-meredith-chao",
    relationships=(
        Relationship(
            person="per-tom-okafor",
            stance="trusts",
            notes="Relies on Tom for clean intake.",
        ),
    ),
    knowledge=(
        KnowledgeItem(
            topic="vendor NDA standard",
            content=(
                "Vendor NDAs must be mutual, two-year term cap, no non-solicit; "
                "unilateral drafts get redlined on sight."
            ),
            share_policy="if_asked",
        ),
    ),
    check_interval_minutes=30,
)


def observed_events() -> list[Event]:
    payloads = [
        (
            0,
            PersonRecordPayload(
                kind="person.record",
                person_id="per-daniel-reyes",
                name="Daniel Reyes",
                email_address="daniel@example.com",
                title="Senior Counsel",
                department="Legal",
                manager=None,
                affiliation="internal",
                timezone="UTC",
            ),
        ),
        (
            0,
            PersonRecordPayload(
                kind="person.record",
                person_id="per-jess-alvarez",
                name="Jess Alvarez",
                email_address="jess@example.com",
                title="Sales Director",
                department="Sales",
                manager=None,
                affiliation="internal",
                timezone="UTC",
            ),
        ),
        (
            0,
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id="cnv-000001",
                conversation_type="channel",
                name="#legal",
                members=("per-daniel-reyes", "per-jess-alvarez"),
            ),
        ),
        (
            34200,
            EmailMessagePayload(
                kind="email.message",
                message_id="msg-000001",
                thread_id="thr-000001",
                in_reply_to=None,
                sender="per-jess-alvarez",
                to=("per-daniel-reyes",),
                cc=(),
                subject="Vendor NDA - need your eyes",
                body="Can you review the attached NDA before Friday?",
                attachments=(),
            ),
        ),
        (
            35000,
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000001",
                conversation_id="cnv-000001",
                reply_to=None,
                sender="per-jess-alvarez",
                body="daniel did you see my email?",
            ),
        ),
    ]
    return [
        Event(seq=seq, time=time, tag=p.kind, source="x", payload=p)
        for seq, (time, p) in enumerate(payloads)
    ]
