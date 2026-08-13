"""Incremental fold of the world log the game master validates against."""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from workbench.core.events import Event
from workbench.core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from workbench.core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from workbench.core.events.email import EmailMessagePayload
from workbench.core.events.people import PersonRecordPayload
from workbench.core.events.tickets import TicketCreatedPayload, TicketUpdatedPayload


class WorldStateModel(BaseModel):
    """The fold, serializable: sorted collections so dumps are byte-stable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    people: tuple[PersonRecordPayload, ...] = ()
    threads: tuple[tuple[str, str], ...] = ()
    message_depth: tuple[tuple[str, int], ...] = ()
    conversations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    conversation_names: tuple[tuple[str, str], ...] = ()
    chat_messages: tuple[str, ...] = ()
    chat_message_conversations: tuple[tuple[str, str], ...] = ()
    documents: tuple[tuple[str, int], ...] = ()
    document_paths: tuple[tuple[str, str], ...] = ()
    tickets: tuple[tuple[str, tuple[tuple[str, str | None], ...]], ...] = Field(
        default=()
    )


class WorldState:
    def __init__(self) -> None:
        self.people: dict[str, PersonRecordPayload] = {}
        self.name_to_person: dict[str, str] = {}
        self.email_to_person: dict[str, str] = {}
        self.threads: dict[str, str] = {}  # message_id -> thread_id
        self.thread_ids: set[str] = set()
        self.message_depth: dict[str, int] = {}  # message_id -> reply depth
        self.conversations: dict[str, tuple[str, ...]] = {}
        self.conversation_names: dict[str, str] = {}  # "#legal" -> id
        self.chat_messages: set[str] = set()
        self.chat_message_conversations: dict[str, str] = {}
        self.documents: dict[str, int] = {}  # id -> head revision
        self.document_paths: dict[str, str] = {}  # path -> id
        self.tickets: dict[str, dict[str, str | None]] = {}

    def apply(self, event: Event) -> None:
        payload = event.payload
        match payload:
            case PersonRecordPayload():
                self.people[payload.person_id] = payload
                self.name_to_person[payload.name.casefold()] = payload.person_id
                self.email_to_person[payload.email_address.casefold()] = (
                    payload.person_id
                )
            case EmailMessagePayload():
                self.threads[payload.message_id] = payload.thread_id
                self.thread_ids.add(payload.thread_id)
                parent_depth = (
                    self.message_depth.get(payload.in_reply_to, 0)
                    if payload.in_reply_to is not None
                    else -1
                )
                self.message_depth[payload.message_id] = parent_depth + 1
            case ChatConversationCreatedPayload():
                self.conversations[payload.conversation_id] = payload.members
                if payload.name:
                    self.conversation_names[payload.name] = payload.conversation_id
            case ChatMessagePayload():
                self.chat_messages.add(payload.chat_message_id)
                self.chat_message_conversations[payload.chat_message_id] = (
                    payload.conversation_id
                )
            case DocumentCreatedPayload():
                self.documents[payload.document_id] = 1
                self.document_paths[payload.path] = payload.document_id
            case DocumentRevisedPayload():
                if payload.document_id in self.documents:
                    self.documents[payload.document_id] = payload.revision
            case TicketCreatedPayload():
                self.tickets[payload.ticket_id] = {
                    "title": payload.title,
                    "description": payload.description,
                    "assignee": payload.assignee,
                    "status": payload.status,
                    "priority": payload.priority,
                }
            case TicketUpdatedPayload():
                values = self.tickets.get(payload.ticket_id)
                if values is not None:
                    for change in payload.changes:
                        if change.field in values:
                            values[change.field] = change.new
            case _:
                pass

    def rebuild(self, events: Iterable[Event]) -> None:
        for event in events:
            self.apply(event)

    def to_model(self) -> WorldStateModel:
        return WorldStateModel(
            people=tuple(
                self.people[person_id] for person_id in sorted(self.people)
            ),
            threads=tuple(sorted(self.threads.items())),
            message_depth=tuple(sorted(self.message_depth.items())),
            conversations=tuple(sorted(self.conversations.items())),
            conversation_names=tuple(sorted(self.conversation_names.items())),
            chat_messages=tuple(sorted(self.chat_messages)),
            chat_message_conversations=tuple(
                sorted(self.chat_message_conversations.items())
            ),
            documents=tuple(sorted(self.documents.items())),
            document_paths=tuple(sorted(self.document_paths.items())),
            tickets=tuple(
                (ticket_id, tuple(sorted(values.items())))
                for ticket_id, values in sorted(self.tickets.items())
            ),
        )

    @classmethod
    def from_model(cls, model: WorldStateModel) -> WorldState:
        state = cls()
        for record in model.people:
            state.people[record.person_id] = record
            state.name_to_person[record.name.casefold()] = record.person_id
            state.email_to_person[record.email_address.casefold()] = record.person_id
        state.threads = dict(model.threads)
        state.thread_ids = set(state.threads.values())
        state.message_depth = dict(model.message_depth)
        state.conversations = {
            conversation_id: tuple(members)
            for conversation_id, members in model.conversations
        }
        state.conversation_names = dict(model.conversation_names)
        state.chat_messages = set(model.chat_messages)
        state.chat_message_conversations = dict(model.chat_message_conversations)
        state.documents = dict(model.documents)
        state.document_paths = dict(model.document_paths)
        state.tickets = {
            ticket_id: dict(values) for ticket_id, values in model.tickets
        }
        return state

    def resolve_person(self, ref: str) -> str | None:
        """Resolve a person ref: exact id, exact name, or unambiguous first name."""
        if ref in self.people:
            return ref
        folded = ref.casefold()
        if folded in self.name_to_person:
            return self.name_to_person[folded]
        if folded in self.email_to_person:
            return self.email_to_person[folded]
        first_name_hits = [
            person_id
            for name, person_id in self.name_to_person.items()
            if name.split()[0] == folded
        ]
        if len(first_name_hits) == 1:
            return first_name_hits[0]
        return None

    def resolve_conversation(self, ref: str) -> str | None:
        if ref in self.conversations:
            return ref
        return self.conversation_names.get(ref)

    def resolve_document(self, ref: str) -> str | None:
        if ref in self.documents:
            return ref
        return self.document_paths.get(ref)
