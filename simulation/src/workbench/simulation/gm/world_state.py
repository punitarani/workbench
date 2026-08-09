"""Incremental fold of the world log the game master validates against."""

from collections.abc import Iterable

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


class WorldState:
    def __init__(self) -> None:
        self.people: dict[str, PersonRecordPayload] = {}
        self.name_to_person: dict[str, str] = {}
        self.email_to_person: dict[str, str] = {}
        self.threads: dict[str, str] = {}  # message_id -> thread_id
        self.thread_ids: set[str] = set()
        self.conversations: dict[str, tuple[str, ...]] = {}
        self.conversation_names: dict[str, str] = {}  # "#legal" -> id
        self.chat_messages: set[str] = set()
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
            case ChatConversationCreatedPayload():
                self.conversations[payload.conversation_id] = payload.members
                if payload.name:
                    self.conversation_names[payload.name] = payload.conversation_id
            case ChatMessagePayload():
                self.chat_messages.add(payload.chat_message_id)
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
