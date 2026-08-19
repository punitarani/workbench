"""Pure folds from an event sequence into read models.

The same folds serve the game master's live world state, per-persona
observation state, and (later) the per-tool database projections.
"""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict

from core.events import Event
from core.events.chat import ChatMessagePayload
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import EmailMessagePayload
from core.events.people import PersonRecordPayload
from core.events.tickets import (
    TicketCommentedPayload,
    TicketCreatedPayload,
    TicketUpdatedPayload,
)
from core.ids import ConversationId, DocumentId, PersonId, ThreadId, TicketId


class TicketSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ticket_id: TicketId
    title: str
    description: str
    requester: PersonId
    assignee: PersonId | None
    status: str
    priority: str
    ticket_type: str
    comments: tuple[str, ...]


class DocumentSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: DocumentId
    title: str
    path: str
    revision: int
    content: str
    author: PersonId


def inbox(events: Iterable[Event], person: PersonId) -> tuple[EmailMessagePayload, ...]:
    return tuple(
        e.payload
        for e in events
        if isinstance(e.payload, EmailMessagePayload)
        and (person in e.payload.to or person in e.payload.cc)
    )


def email_thread(
    events: Iterable[Event], thread_id: ThreadId
) -> tuple[EmailMessagePayload, ...]:
    return tuple(
        e.payload
        for e in events
        if isinstance(e.payload, EmailMessagePayload)
        and e.payload.thread_id == thread_id
    )


def conversation(
    events: Iterable[Event], conversation_id: ConversationId
) -> tuple[ChatMessagePayload, ...]:
    return tuple(
        e.payload
        for e in events
        if isinstance(e.payload, ChatMessagePayload)
        and e.payload.conversation_id == conversation_id
    )


def ticket_snapshot(events: Iterable[Event], ticket_id: TicketId) -> TicketSnapshot:
    created: TicketCreatedPayload | None = None
    values: dict[str, str | None] = {}
    comments: list[str] = []
    for event in events:
        payload = event.payload
        if isinstance(payload, TicketCreatedPayload) and payload.ticket_id == ticket_id:
            created = payload
            values = {
                "title": payload.title,
                "description": payload.description,
                "assignee": payload.assignee,
                "status": payload.status,
                "priority": payload.priority,
            }
        elif (
            isinstance(payload, TicketUpdatedPayload) and payload.ticket_id == ticket_id
        ):
            for change in payload.changes:
                if change.field in values:
                    values[change.field] = change.new
        elif (
            isinstance(payload, TicketCommentedPayload)
            and payload.ticket_id == ticket_id
        ):
            comments.append(payload.body)
    if created is None:
        raise KeyError(f"ticket {ticket_id} was never created")
    return TicketSnapshot(
        ticket_id=ticket_id,
        title=values["title"] or created.title,
        description=values["description"] or created.description,
        requester=created.requester,
        assignee=PersonId(values["assignee"]) if values["assignee"] else None,
        status=values["status"] or created.status,
        priority=values["priority"] or created.priority,
        ticket_type=created.ticket_type,
        comments=tuple(comments),
    )


def document_head(events: Iterable[Event], document_id: DocumentId) -> DocumentSnapshot:
    snapshot: DocumentSnapshot | None = None
    for event in events:
        payload = event.payload
        if (
            isinstance(payload, DocumentCreatedPayload)
            and payload.document_id == document_id
        ):
            snapshot = DocumentSnapshot(
                document_id=document_id,
                title=payload.title,
                path=payload.path,
                revision=1,
                content=payload.content,
                author=payload.author,
            )
        elif (
            isinstance(payload, DocumentRevisedPayload)
            and payload.document_id == document_id
            and snapshot is not None
        ):
            snapshot = snapshot.model_copy(
                update={
                    "revision": payload.revision,
                    "content": payload.content,
                    "author": payload.author,
                }
            )
    if snapshot is None:
        raise KeyError(f"document {document_id} was never created")
    return snapshot


def directory(events: Iterable[Event]) -> tuple[PersonRecordPayload, ...]:
    return tuple(
        e.payload for e in events if isinstance(e.payload, PersonRecordPayload)
    )
