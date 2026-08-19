"""A small coherent event sequence for harness tests.

Mirrors tools/tests/projection_fixtures.py and
workbench/tests/worldlog_fixtures.py; each member test suite is
self-contained, so keep edits in every copy. Named distinctly because the
test directories share one pytest import namespace."""

from core.events import Event, EventPayload
from core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from core.events.control import SimRunStartedPayload
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import EmailMessagePayload
from core.events.people import PersonRecordPayload
from core.events.tickets import (
    FieldChange,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)

PEOPLE = ("per-meredith-chao", "per-daniel-reyes", "per-tom-okafor", "per-jess-alvarez")


def _person(person_id: str, name: str) -> PersonRecordPayload:
    return PersonRecordPayload(
        kind="person.record",
        person_id=person_id,
        name=name,
        email_address=f"{name.split()[0].lower()}@example.com",
        title="Counsel",
        department="Legal",
        manager=None,
        affiliation="internal",
        timezone="America/Los_Angeles",
    )


def coherent_events() -> list[Event]:
    payloads: list[tuple[int, str, EventPayload]] = [
        (
            0,
            "gm",
            SimRunStartedPayload(
                kind="sim.run.started",
                run_id="run-fixture",
                seed_root=7,
                workplace_id="legal-demo",
                config_hash="0" * 64,
                schema_version=1,
                epoch="2026-03-12T00:00:00-07:00",
                timezone="America/Los_Angeles",
            ),
        ),
        (0, "gm", _person("per-meredith-chao", "Meredith Chao")),
        (0, "gm", _person("per-daniel-reyes", "Daniel Reyes")),
        (0, "gm", _person("per-tom-okafor", "Tom Okafor")),
        (0, "gm", _person("per-jess-alvarez", "Jess Alvarez")),
        (
            0,
            "gm",
            ChatConversationCreatedPayload(
                kind="chat.conversation.created",
                conversation_id="cnv-000001",
                conversation_type="channel",
                name="#legal",
                members=("per-meredith-chao", "per-daniel-reyes", "per-tom-okafor"),
            ),
        ),
        (
            100,
            "gm",
            DocumentCreatedPayload(
                kind="document.created",
                document_id="doc-000001",
                author="per-daniel-reyes",
                title="NDA Playbook",
                path="/legal/playbooks/nda-playbook.md",
                location="repository",
                content_format="markdown",
                content="v1",
            ),
        ),
        (
            200,
            "jess",
            EmailMessagePayload(
                kind="email.message",
                message_id="msg-000001",
                thread_id="thr-000001",
                in_reply_to=None,
                sender="per-jess-alvarez",
                to=("per-tom-okafor",),
                cc=("per-meredith-chao",),
                subject="NDA review",
                body="Please review.",
                attachments=(),
            ),
        ),
        (
            300,
            "tom",
            TicketCreatedPayload(
                kind="ticket.created",
                ticket_id="tkt-000001",
                actor="per-tom-okafor",
                title="Review NDA",
                description="Inbound NDA.",
                requester="per-jess-alvarez",
                assignee="per-daniel-reyes",
                status="open",
                priority="normal",
                ticket_type="nda-review",
                fields=(),
            ),
        ),
        (
            400,
            "tom",
            EmailMessagePayload(
                kind="email.message",
                message_id="msg-000002",
                thread_id="thr-000001",
                in_reply_to="msg-000001",
                sender="per-tom-okafor",
                to=("per-jess-alvarez",),
                cc=(),
                subject="Re: NDA review",
                body="Filed as MTR-1, Daniel will review.",
                attachments=(),
            ),
        ),
        (
            500,
            "daniel",
            ChatMessagePayload(
                kind="chat.message",
                chat_message_id="chm-000001",
                conversation_id="cnv-000001",
                reply_to=None,
                sender="per-daniel-reyes",
                body="Taking the NDA review.",
            ),
        ),
        (
            600,
            "daniel",
            TicketUpdatedPayload(
                kind="ticket.updated",
                ticket_id="tkt-000001",
                actor="per-daniel-reyes",
                changes=(FieldChange(field="status", old="open", new="in-review"),),
            ),
        ),
        (
            700,
            "daniel",
            DocumentRevisedPayload(
                kind="document.revised",
                document_id="doc-000001",
                revision=2,
                author="per-daniel-reyes",
                content="v2",
                change_summary="Update playbook.",
            ),
        ),
    ]
    return [
        Event(seq=seq, time=time, tag=payload.kind, source=source, payload=payload)
        for seq, (time, source, payload) in enumerate(payloads)
    ]
