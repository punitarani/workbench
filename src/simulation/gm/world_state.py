"""Incremental fold of the world log the game master validates against."""

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from core.events import Event
from core.events.agent import SimAgentPlanPayload
from core.events.calendar import CalendarEventScheduledPayload
from core.events.chat import (
    ChatConversationCreatedPayload,
    ChatMessagePayload,
)
from core.events.control import SimWakePayload
from core.events.documents import (
    DocumentCreatedPayload,
    DocumentRevisedPayload,
)
from core.events.email import EmailMessagePayload
from core.events.meetings import (
    MeetingTranscriptPayload,
    SimMeetingConvenePayload,
    TranscriptTurn,
)
from core.events.people import PersonRecordPayload
from core.events.tickets import TicketCreatedPayload, TicketUpdatedPayload
from core.filing import filed_name


class MeetingProgress(BaseModel):
    """An in-flight meeting: opened at convene, closed at transcript."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    meeting_id: str
    calendar_event_id: str | None
    title: str
    description: str = ""
    attendees: tuple[str, ...]  # entity names
    started: int
    budget: int
    turns: tuple[TranscriptTurn, ...] = ()
    yielded: tuple[str, ...] = ()


class WorldStateModel(BaseModel):
    """The fold, serializable: sorted collections so dumps are byte-stable."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    people: tuple[PersonRecordPayload, ...] = ()
    threads: tuple[tuple[str, str], ...] = ()
    thread_participants: tuple[tuple[str, tuple[str, ...]], ...] = ()
    message_depth: tuple[tuple[str, int], ...] = ()
    conversations: tuple[tuple[str, tuple[str, ...]], ...] = ()
    conversation_names: tuple[tuple[str, str], ...] = ()
    chat_messages: tuple[str, ...] = ()
    chat_thread_roots: tuple[tuple[str, str], ...] = ()
    chat_message_conversations: tuple[tuple[str, str], ...] = ()
    documents: tuple[tuple[str, int], ...] = ()
    calendar_events: tuple[str, ...] = ()
    # Who called each meeting. Kept so an RSVP can reach the person it is
    # an answer to; defaulted so a state recorded before this existed
    # still loads.
    calendar_organizers: tuple[tuple[str, str], ...] = ()
    document_paths: tuple[tuple[str, str], ...] = ()
    document_formats: tuple[tuple[str, str], ...] = ()
    document_authors: tuple[tuple[str, str], ...] = ()
    document_heads: tuple[tuple[str, str], ...] = ()
    standing_tickets: tuple[str, ...] = ()
    tickets: tuple[tuple[str, tuple[tuple[str, str | None], ...]], ...] = Field(
        default=()
    )
    # "entity|day" -> latest plan revision, so replans number deterministically.
    plan_revisions: tuple[tuple[str, int], ...] = ()
    meetings: tuple[MeetingProgress, ...] = ()
    # conversation_id -> consecutive auto-granted chat run length.
    chat_streaks: tuple[tuple[str, int], ...] = ()
    chat_message_senders: tuple[tuple[str, str], ...] = ()
    last_chat_message: tuple[tuple[str, str], ...] = ()


class WorldState:
    def __init__(self) -> None:
        self.people: dict[str, PersonRecordPayload] = {}
        self.name_to_person: dict[str, str] = {}
        self.email_to_person: dict[str, str] = {}
        self.threads: dict[str, str] = {}  # message_id -> thread_id
        self.thread_ids: set[str] = set()
        # Everyone who has written in a thread, by thread id. Kept so a
        # reply can be addressed from the thread it replies to instead of
        # being refused for restating what is already in front of the
        # persona -- see `_ground_email`.
        self.thread_participants: dict[str, set[str]] = {}
        self.message_depth: dict[str, int] = {}  # message_id -> reply depth
        self.conversations: dict[str, tuple[str, ...]] = {}
        self.conversation_names: dict[str, str] = {}  # "#legal" -> id
        self.chat_messages: set[str] = set()
        self.chat_thread_roots: dict[str, str] = {}
        self.chat_message_conversations: dict[str, str] = {}
        self.documents: dict[str, int] = {}  # id -> head revision
        self.document_paths: dict[str, str] = {}  # path -> id
        # An attachment needs the file's name and kind, so the fold keeps
        # both directions of the document mapping.
        self.document_paths_by_id: dict[str, str] = {}  # id -> path
        self.document_formats: dict[str, str] = {}  # id -> content format
        # Who wrote it and what it currently says: a revision turn needs
        # both to carry a document forward rather than start a new one.
        self.document_authors: dict[str, str] = {}
        self.document_heads: dict[str, str] = {}
        self.tickets: dict[str, dict[str, str | None]] = {}
        # Institution-wide codes anybody may book to, declared by the
        # world rather than inferred from a ticket having no client — a
        # persona's runtime tickets have no client either.
        self.standing_tickets: set[str] = set()
        # Filed name -> the document that holds it. Reserved when a create
        # is *resolved*, not when its event lands: a cohort's creates all
        # resolve before any draft is applied, so keying off applied state
        # let three documents reach one file with no rejection.
        self.documents_by_filed_name: dict[str, str] = {}
        self.plan_revisions: dict[str, int] = {}
        self.meetings: dict[str, MeetingProgress] = {}
        # Invitations can only be answered for meetings that exist.
        self.calendar_events: set[str] = set()
        self.calendar_organizers: dict[str, str] = {}
        self.chat_streaks: dict[str, int] = {}
        self.chat_message_senders: dict[str, str] = {}
        self.last_chat_message: dict[str, str] = {}

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
                self.thread_participants.setdefault(payload.thread_id, set()).update(
                    (payload.sender, *payload.to, *payload.cc)
                )
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
                # Which thread this message belongs to. A chat thread is
                # one level deep in the product these surfaces mirror:
                # every reply carries the *root's* timestamp, and there is
                # no reply-to-a-reply. Keeping the root here is what lets
                # the referee flatten a chain before it reaches the log.
                self.chat_thread_roots[payload.chat_message_id] = (
                    self.chat_thread_roots.get(payload.reply_to, payload.reply_to)
                    if payload.reply_to
                    else payload.chat_message_id
                )
                self.chat_message_conversations[payload.chat_message_id] = (
                    payload.conversation_id
                )
                self.chat_message_senders[payload.chat_message_id] = payload.sender
                self.last_chat_message[payload.conversation_id] = (
                    payload.chat_message_id
                )
                # Counted for every conversation, not only two-person
                # ones. The brake this feeds guarded DMs alone, and the
                # channel reply path had no cap of any kind -- harmless
                # while replying was effectively impossible (3 replies in
                # 3,177 messages), and a runaway the moment pending items
                # started naming a message to reply to. Two personas in a
                # channel volley with nothing to stop them, and a chat
                # delay of 30s + body/30 admits hundreds of exchanges in
                # one simulated day.
                self.chat_streaks[payload.conversation_id] = (
                    self.chat_streaks.get(payload.conversation_id, 0) + 1
                )
            case DocumentCreatedPayload():
                self.documents[payload.document_id] = 1
                self.document_paths[payload.path] = payload.document_id
                self.document_paths_by_id[payload.document_id] = payload.path
                self.document_formats[payload.document_id] = payload.content_format
                self.documents_by_filed_name.setdefault(
                    filed_name(payload.path, payload.content_format),
                    payload.document_id,
                )
                self.document_authors[payload.document_id] = payload.author
                self.document_heads[payload.document_id] = payload.content
            case DocumentRevisedPayload():
                if payload.document_id in self.documents:
                    self.documents[payload.document_id] = payload.revision
                    self.document_heads[payload.document_id] = payload.content
            case TicketCreatedPayload():
                if payload.standing:
                    # Kept beside the ticket dict rather than inside it:
                    # that dict serialises as `str | None` values, and a
                    # bool in there breaks every snapshot restore.
                    self.standing_tickets.add(payload.ticket_id)
                self.tickets[payload.ticket_id] = {
                    "title": payload.title,
                    "description": payload.description,
                    "assignee": payload.assignee,
                    "status": payload.status,
                    "priority": payload.priority,
                    # No client means the institution's own standing work:
                    # administration, internal meetings, business
                    # development. Anyone may book to it, so it must survive
                    # the truncation below.
                    "client_ref": payload.client_ref,
                }
            case TicketUpdatedPayload():
                values = self.tickets.get(payload.ticket_id)
                if values is not None:
                    for change in payload.changes:
                        if change.field in values:
                            values[change.field] = change.new
            case SimAgentPlanPayload():
                key = f"{payload.entity}|{payload.day}"
                self.plan_revisions[key] = payload.revision
            case SimWakePayload():
                # A wake is a beat in the day: chat bursts end, streaks reset.
                self.chat_streaks.clear()
            case CalendarEventScheduledPayload():
                self.calendar_events.add(payload.calendar_event_id)
                self.calendar_organizers[payload.calendar_event_id] = payload.organizer
            case SimMeetingConvenePayload():
                self.meetings[payload.meeting_id] = MeetingProgress(
                    meeting_id=payload.meeting_id,
                    calendar_event_id=payload.calendar_event_id,
                    title=payload.title,
                    description=payload.description,
                    attendees=payload.attendees,
                    started=int(event.time),
                    budget=max(4, min(12, payload.duration_seconds // 180)),
                )
            case MeetingTranscriptPayload():
                self.meetings.pop(payload.meeting_id, None)
            case _:
                pass

    def rebuild(self, events: Iterable[Event]) -> None:
        for event in events:
            self.apply(event)

    def to_model(self) -> WorldStateModel:
        return WorldStateModel(
            people=tuple(self.people[person_id] for person_id in sorted(self.people)),
            threads=tuple(sorted(self.threads.items())),
            thread_participants=tuple(
                (thread, tuple(sorted(people)))
                for thread, people in sorted(self.thread_participants.items())
            ),
            message_depth=tuple(sorted(self.message_depth.items())),
            conversations=tuple(sorted(self.conversations.items())),
            conversation_names=tuple(sorted(self.conversation_names.items())),
            chat_messages=tuple(sorted(self.chat_messages)),
            chat_thread_roots=tuple(sorted(self.chat_thread_roots.items())),
            chat_message_conversations=tuple(
                sorted(self.chat_message_conversations.items())
            ),
            documents=tuple(sorted(self.documents.items())),
            calendar_events=tuple(sorted(self.calendar_events)),
            calendar_organizers=tuple(sorted(self.calendar_organizers.items())),
            document_paths=tuple(sorted(self.document_paths.items())),
            document_formats=tuple(sorted(self.document_formats.items())),
            document_authors=tuple(sorted(self.document_authors.items())),
            document_heads=tuple(sorted(self.document_heads.items())),
            standing_tickets=tuple(sorted(self.standing_tickets)),
            tickets=tuple(
                (ticket_id, tuple(sorted(values.items())))
                for ticket_id, values in sorted(self.tickets.items())
            ),
            plan_revisions=tuple(sorted(self.plan_revisions.items())),
            meetings=tuple(self.meetings[key] for key in sorted(self.meetings)),
            chat_streaks=tuple(sorted(self.chat_streaks.items())),
            chat_message_senders=tuple(sorted(self.chat_message_senders.items())),
            last_chat_message=tuple(sorted(self.last_chat_message.items())),
        )

    @classmethod
    def from_model(cls, model: WorldStateModel) -> WorldState:
        state = cls()
        for record in model.people:
            state.people[record.person_id] = record
            state.name_to_person[record.name.casefold()] = record.person_id
            state.email_to_person[record.email_address.casefold()] = record.person_id
        state.threads = dict(model.threads)
        state.thread_participants = {
            thread: set(people) for thread, people in model.thread_participants
        }
        state.thread_ids = set(state.threads.values())
        state.message_depth = dict(model.message_depth)
        state.conversations = {
            conversation_id: tuple(members)
            for conversation_id, members in model.conversations
        }
        state.conversation_names = dict(model.conversation_names)
        state.chat_messages = set(model.chat_messages)
        state.chat_thread_roots = dict(model.chat_thread_roots)
        state.chat_message_conversations = dict(model.chat_message_conversations)
        state.documents = dict(model.documents)
        state.calendar_events = set(model.calendar_events)
        state.calendar_organizers = dict(model.calendar_organizers)
        state.document_paths = dict(model.document_paths)
        state.document_paths_by_id = {
            document_id: path for path, document_id in model.document_paths
        }
        state.document_formats = dict(model.document_formats)
        state.document_authors = dict(model.document_authors)
        state.document_heads = dict(model.document_heads)
        state.tickets = {ticket_id: dict(values) for ticket_id, values in model.tickets}
        state.standing_tickets = set(model.standing_tickets)
        # Rebuilt rather than serialised: it is a pure function of the
        # paths and formats already restored above, so it cannot drift.
        state.documents_by_filed_name = {}
        for document_id, path in state.document_paths_by_id.items():
            state.documents_by_filed_name.setdefault(
                filed_name(path, state.document_formats.get(document_id, "markdown")),
                document_id,
            )
        state.plan_revisions = dict(model.plan_revisions)
        state.meetings = {m.meeting_id: m for m in model.meetings}
        state.chat_streaks = dict(model.chat_streaks)
        state.chat_message_senders = dict(model.chat_message_senders)
        state.last_chat_message = dict(model.last_chat_message)
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

    def knows_ref(self, ref: str) -> bool:
        """Does this typed id resolve against the folded world?"""
        return (
            ref in self.people
            or ref in self.thread_ids
            or ref in self.threads
            or ref in self.conversations
            or ref in self.chat_messages
            or ref in self.documents
            or ref in self.tickets
            or ref in self.calendar_events
        )
